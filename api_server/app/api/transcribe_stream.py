# app/api/transcribe_stream.py
from __future__ import annotations

import asyncio
import os
import time
import logging
import contextlib
from typing import Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.voice_phishing_service import (
    get_detector,
    create_session,
    HybridPhishingSession,
)
from app.services.stt_adapter import WebsocketSTTStream, GrpcSTTStream

# gRPC STT 에러 잡기용
from grpc.aio import AioRpcError

import numpy as np  # 🔴 추가: 볼륨 계산을 위한 numpy 추가

router = APIRouter(prefix="/api/transcribe", tags=["Transcribe (Realtime)"])

logger = logging.getLogger("transcribe_stream")


def _stt_factory(sample_rate: int):
    provider = os.getenv("STT_PROVIDER", "grpc")  # "grpc" | "ws"
    if provider == "ws":
        url = os.getenv("STT_WS_URL", "wss://stt.example.com/stream")
        logger.info(f"STT_PROVIDER=ws, url={url}")
        return WebsocketSTTStream(url, sample_rate)
    logger.info("STT_PROVIDER=grpc")
    return GrpcSTTStream(sample_rate)


def _now() -> float:
    return time.time()


async def _send_json(ws: WebSocket, payload: dict):
    """공통 JSON 송신 + 간단 로깅"""
    import json

    data = json.dumps(payload, ensure_ascii=False)
    # 너무 많이 찍히면 noisy 할 수 있으니, 필요하면 주석 처리
    if payload.get("kind") in {"partial", "final", "risk", "error", "state"}:
        logger.debug(f"[WS->CLIENT] {data}")
    await ws.send_text(data)


# 🔴 추가: PCM16 볼륨 계산 함수
def calculate_volume(pcm_bytes: bytes) -> float:
    """
    PCM16 mono 오디오 볼륨 계산 (0.0 ~ 1.0)
    RMS 기반으로 계산하여 음성이 들어오는지 판단할 수 있게 한다
    """
    if len(pcm_bytes) < 2:
        return 0.0

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(samples * samples))
    return min(rms / 32768.0, 1.0)


@router.websocket("/ws")
async def transcribe_ws(
    ws: WebSocket,
    sr: int = Query(16000, ge=8000, le=48000),
    lang: str = Query("ko-KR"),
    client: str = Query("unknown"),
):
    """
    WebSocket 엔드포인트
    - sr: sample rate (기본 16k)
    - lang: ko-KR, en-US ...
    - client: "web", "android" 등 구분용 (디버깅에 도움)
    """
    await ws.accept()
    logger.info(f"[WS OPEN] client={client} sr={sr} lang={lang}")
    await _send_json(ws, {"kind": "state", "text": "ready", "t": _now()})

    # 전역 단일 모델 로딩→ 세션 생성
    detector = get_detector()
    session: HybridPhishingSession = create_session(window_size=5)

    stt = _stt_factory(sr)

    recv_task = asyncio.create_task(_recv_audio(ws, stt))
    send_task = asyncio.create_task(_pump(ws, stt, session, client))

    try:
        await asyncio.gather(recv_task, send_task)

    except WebSocketDisconnect:
        # 클라이언트가 끊은 경우
        logger.info(f"[WS DISCONNECT] client={client}")

    except asyncio.CancelledError:
        # gRPC 스트림 / 태스크가 취소되면서 올라오는 CancelledError
        logger.info(f"[WS CANCELLED] client={client} - streaming cancelled")
        # 여기서 다시 raise 안 하고 조용히 종료

    finally:
        # STT 스트림 정리 (여기서만 close 호출하도록 통일)
        try:
            await stt.close()
        except Exception as e:
            logger.warning(f"stt.close() 에서 예외 발생: {e!r}")

        session.reset()

        for t in (recv_task, send_task):
            if not t.done():
                t.cancel()

        logger.info(f"[WS CLOSED] client={client}")


async def _recv_audio(ws: WebSocket, stt):
    """
    클라이언트에서 오는 PCM 바이너리 / 제어 메시지를 STT로 넘기는 루프.
    - 바이너리: stt.feed(...)
    - "__END__": STT 종료(close) 후 루프 종료
    - disconnect: STT 종료(close) 후 루프 종료
    """
    try:
        while True:
            # 일부 Starlette 버전에서 disconnect 이후에 receive를 더 부르면
            # RuntimeError('Cannot call "receive"...') 를 던지므로 방어
            try:
                msg = await ws.receive()
            except RuntimeError as e:
                logger.warning(f"_recv_audio RuntimeError: {e}")
                # 이미 disconnect 메시지를 처리한 뒤 추가 receive 호출된 경우
                break

            msg_type = msg.get("type")

            # 클라이언트가 연결을 끊은 경우 (ASGI 메시지 타입 기준)
            if msg_type == "websocket.disconnect":
                logger.info("_recv_audio: websocket.disconnect 수신 → STT close 후 종료")
                with contextlib.suppress(Exception):
                    await stt.close()
                break

            # 정상 수신 메시지
            if msg_type == "websocket.receive":
                if (b := msg.get("bytes")) is not None:
                    # PCM 바이너리 → STT 입력
                    # 🔵 수정: 기존 len 출력 → 볼륨까지 함께 출력
                    vol = calculate_volume(b)
                    logger.info("recv bytes len=%s, volume=%.2f", len(b), vol)

                    await stt.feed(b)

                elif (t := msg.get("text")) is not None:
                    # 제어 텍스트 프레임 처리
                    if t == "__END__":
                        logger.info('_recv_audio: "__END__" 수신 → STT close 후 종료')
                        # 🔴 STT 종료 신호 (audio_q에 None 넣어줌)
                        with contextlib.suppress(Exception):
                            await stt.close()
                        break

    except WebSocketDisconnect:
        # 다른 Starlette/FastAPI 버전에서는 여기로 들어올 수 있음
        logger.info("_recv_audio: WebSocketDisconnect 발생")
        with contextlib.suppress(Exception):
            await stt.close()
    # transcribe_ws 의 finally 에서도 한 번 더 close() 시도 (중복 호출 안전)


async def _pump(ws: WebSocket, stt, session: HybridPhishingSession, client: str):
    """
    STT에서 (text, is_final) 스트림을 받아
    - partial: word 기반 즉시 분석만 수행해 전송
    - final:   즉시 분석 + 누적(KoBERT) 분석까지 수행해 전송
    """
    try:
        async with stt:
            logger.info(f"[STT START] client=%s", client)

            async for text, is_final in stt.transcripts():
                logger.info(f"[STT TEXT] client={client} final={is_final} text={text!r}")

                text = (text or "").strip()
                if not text:
                    continue

                fragment = session.process_fragment(text, is_final)
                payload = {
                    "kind": "partial" if not is_final else "final",
                    "text": text,
                    "immediate": fragment["immediate"],
                    "t": _now(),
                }
                if fragment.get("chunk_immediate"):
                    payload["chunk_immediate"] = fragment["chunk_immediate"]
                if fragment.get("history"):
                    payload["history"] = fragment.get("history")
                await _send_json(ws, payload)

                comprehensive = fragment.get("comprehensive")
                if comprehensive:
                    await _send_json(
                        ws,
                        {
                            "kind": "risk",
                            "text": text,
                            "immediate": fragment["immediate"],
                            "comprehensive": comprehensive,  # is_phishing/confidence 포함
                            "t": _now(),
                            "history": fragment.get("history"),
                        },
                    )

    except AioRpcError as e:
        # 🔴 클로바 STT 쪽에서 io exception / UNAVAILABLE 등 던질 때 여기로 옴
        code = e.code()
        detail = e.details()
        logger.error(
            f"[STT RPC ERROR] client={client} code={getattr(code, 'name', code)} detail={detail}"
        )
        logger.error("%s %s", e.code(), e.details())
        try:
            await _send_json(
                ws,
                {
                    "kind": "error",
                    "error": "stt_unavailable",
                    "grpc_status": getattr(code, "name", str(code)),
                    "detail": detail or "STT backend unavailable",
                    "t": _now(),
                },
            )
        except Exception:
            pass

    except WebSocketDisconnect:
        logger.info(f"_pump: WebSocketDisconnect (client={client})")

    except Exception as e:
        logger.exception(f"_pump: unexpected error (client={client})")
        try:
            await _send_json(
                ws,
                {
                    "kind": "error",
                    "error": "internal_error",
                    "detail": str(e),
                    "t": _now(),
                },
            )
        except Exception:
            pass


@router.get("/ws-info")
def ws_info():
    base = os.getenv("PUBLIC_WS_BASE", "ws://127.0.0.1:8000")
    return {
        "connect_to": f"{base}/api/transcribe/ws?sr=16000",
        "send": "PCM16LE mono 16kHz 바이너리(예: 200ms)",
        "end": "__END__ (text frame)",
        "receive": "JSON: kind=partial/final/risk",
    }
