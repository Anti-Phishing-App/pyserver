# app/api/transcribe_stream.py
from __future__ import annotations
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio, os, time
from typing import Optional, Tuple

# ==== 당신이 이미 가진 탐지기 모듈 사용 ====
# 파일 경로/모듈명은 실제 위치에 맞춰 조정하세요.
from app.services.voice_phishing_service import get_detector, create_session, HybridPhishingSession

# STT 어댑터 (WS / gRPC 중 택1)
from app.services.stt_adapter import WebsocketSTTStream, GrpcSTTStream

router = APIRouter(prefix="/api/transcribe", tags=["Transcribe (Realtime)"])



def _stt_factory(sample_rate: int):
    provider = os.getenv("STT_PROVIDER", "grpc")  # "grpc" | "ws"
    if provider == "ws":
        url = os.getenv("STT_WS_URL", "wss://stt.example.com/stream")
        return WebsocketSTTStream(url, sample_rate)
    return GrpcSTTStream(sample_rate)

def _now() -> float:
    return time.time()

async def _send_json(ws: WebSocket, payload: dict):
    # pydantic 없이 바로 dict→json 문자열로 보내도 됨
    import json
    await ws.send_text(json.dumps(payload, ensure_ascii=False))

@router.websocket("/ws")
async def transcribe_ws(ws: WebSocket, sr: int = Query(16000, ge=8000, le=48000)):
    await ws.accept()
    await _send_json(ws, {"kind": "state", "text": "ready", "t": _now()})

    # 전역 단일 모델 로딩→ 세션 생성
    detector = get_detector()
    session: HybridPhishingSession = create_session(window_size=5)

    stt = _stt_factory(sr)
    recv_task = asyncio.create_task(_recv_audio(ws, stt))
    send_task = asyncio.create_task(_pump(ws, stt, session))

    try:
        await asyncio.gather(recv_task, send_task)
    except WebSocketDisconnect:
        pass
    finally:
        await stt.close()
        session.reset()
        for t in (recv_task, send_task):
            if not t.done():
                t.cancel()

async def _recv_audio(ws: WebSocket, stt):
    while True:
        msg = await ws.receive()
        if (b := msg.get("bytes")) is not None:
            await stt.feed(b)
        elif (t := msg.get("text")) is not None and t == "__END__":
            await stt.close()
            break

async def _pump(ws: WebSocket, stt, session: HybridPhishingSession):
    """
    STT에서 (text, is_final) 스트림을 받아
    - partial: word 기반 즉시 분석만 수행해 전송
    - final:   즉시 분석 + 누적(KoBERT) 분석까지 수행해 전송
    """
    async with stt:
        async for text, is_final in stt.transcripts():
            text = (text or "").strip()
            if not text:
                continue

            # 1) 즉시(단어 기반) — 한 문장에도 빠르게
            immediate = session.detector.detect_immediate(text)
            await _send_json(ws, {
                "kind": "partial" if not is_final else "final",
                "text": text,
                "immediate": immediate,  # level/probability/keywords 등 포함
                "t": _now()
            })

            # 2) 문장 경계일 때 누적(KoBERT)까지
            if is_final:
                both = session.add_sentence(text)  # 내부에서 detect_immediate + (>=3문장 시) detect_comprehensive
                # comprehensive가 있을 수도/없을 수도 있음(3문장 미만)
                if both.get("comprehensive"):
                    await _send_json(ws, {
                        "kind": "risk",
                        "text": text,
                        "immediate": both["immediate"],
                        "comprehensive": both["comprehensive"],  # is_phishing/confidence 포함
                        "t": _now()
                    })

@router.get("/ws-info")
def ws_info():
    base = os.getenv("PUBLIC_WS_BASE", "ws://127.0.0.1:8000")
    return {
        "connect_to": f"{base}/api/transcribe/ws?sr=16000",
        "send": "PCM16LE mono 16kHz 바이너리(예: 200ms)",
        "end": "__END__ (text frame)",
        "receive": "JSON: kind=partial/final/risk"
    }