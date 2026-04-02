"""음성 인식 API (CLOVA Speech)"""
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, Field
import httpx
import grpc

from app.config import (
    CLOVA_LONG_INVOKE_URL,
    CLOVA_LONG_SECRET_KEY,
    CLOVA_GRPC_SECRET_KEY,
    CLOVA_GRPC_HOST,
    CLOVA_GRPC_PORT,
)

from grpc_client.clova_grpc_client import ClovaSpeechClient
from app.services.voice_phishing_service import create_session

router = APIRouter()


# =====================================================================================
# 저장된 녹음 파일 인식 (CLOVA Speech REST)
# =====================================================================================
class TranscriptionParams(BaseModel):
    language: str = Field("ko-KR")
    completion: str = Field("async")
    wordAlignment: bool = Field(True)
    fullText: bool = Field(True)


@router.post("/api/transcribe/upload")
async def transcribe_file_upload(
    media: UploadFile = File(...),
    language: str = Form("ko-KR"),
    completion: str = Form("async")
):
    # 🔥 장문 전용 키 사용
    if not CLOVA_LONG_INVOKE_URL or not CLOVA_LONG_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLOVA_LONG 환경변수 필요")

    headers = {"X-CLOVASPEECH-API-KEY": CLOVA_LONG_SECRET_KEY}

    file_bytes = await media.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)

    if completion == "auto":
        completion = "sync" if file_size_mb <= 1 else "async"

    callback_url = "http://13.125.25.96:8000/api/transcribe/callback"

    params_dict = {
        "language": language,
        "completion": completion,
        "callback": callback_url if completion == "async" else None,
        "wordAlignment": True,
        "fullText": True,
    }

    params_dict = {k: v for k, v in params_dict.items() if v is not None}
    params_json = json.dumps(params_dict, ensure_ascii=False)

    files = {
        "media": (media.filename, file_bytes, media.content_type),
        "params": (None, params_json, "application/json"),
    }

    clova_url = f"{CLOVA_LONG_INVOKE_URL}/recognizer/upload"

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        try:
            resp = await client.post(clova_url, headers=headers, files=files)
            resp.raise_for_status()
            return {"mode": completion, "response": resp.json()}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code,
                                detail=f"CLOVA API Error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"CLOVA API 요청 실패: {e}")


@router.post("/api/transcribe/callback")
async def clova_callback(request: Request):
    raw_body = await request.body()

    if not raw_body:
        return {"status": "ok", "empty": True}

    text_body = raw_body.decode("utf-8", errors="ignore").strip()

    try:
        payload = json.loads(text_body)
        print("[CALLBACK JSON]", payload)
        return {"status": "ok", "json": True}
    except:
        print("[CALLBACK TEXT]", text_body)
        return {"status": "ok", "text": text_body}


@router.get("/api/transcribe/status/{token}")
async def transcribe_status(token: str):
    # 🔥 장문 전용 키
    if not CLOVA_LONG_INVOKE_URL or not CLOVA_LONG_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLOVA_LONG 환경변수 필요")

    headers = {"X-CLOVASPEECH-API-KEY": CLOVA_LONG_SECRET_KEY}
    clova_url = f"{CLOVA_LONG_INVOKE_URL}/recognizer/{token}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.get(clova_url, headers=headers)
        resp.raise_for_status()
        return resp.json()


# =====================================================================================
# 실시간 스트리밍 (gRPC)
# =====================================================================================
@router.websocket("/ws/transcribe/stream")
async def websocket_transcribe_stream(
    websocket: WebSocket,
    lang: str = "ko-KR",
    enable_phishing_detection: bool = True
):
    await websocket.accept()

    grpc_client: ClovaSpeechClient | None = None
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    response_task: asyncio.Task | None = None
    phishing_session = None

    try:
        # 🔥 gRPC 전용 키 체크
        if not CLOVA_GRPC_SECRET_KEY:
            raise RuntimeError("CLOVA_GRPC_SECRET_KEY 필요")

        if enable_phishing_detection:
            try:
                phishing_session = create_session(window_size=5)
            except Exception:
                enable_phishing_detection = False

        # 🔥 핵심 (분리 완료)
        grpc_client = ClovaSpeechClient(
            secret_key=CLOVA_GRPC_SECRET_KEY,
            host=CLOVA_GRPC_HOST,
            port=CLOVA_GRPC_PORT,
        )

        lang_short = (lang or "ko-KR").split("-")[0].lower()

        config_json = json.dumps({
            "transcription": {"language": lang_short},
            "semanticEpd": {
                "skipEmptyText": True,
                "useWordEpd": False,
                "usePeriodEpd": True,
            }
        })

        async def response_handler():
            async for response in grpc_client.recognize(
                audio_queue,
                config_json=config_json,
                language=lang,
            ):
                contents = getattr(response, "contents", "")
                if not contents:
                    continue

                try:
                    payload = json.loads(contents)
                    tr = payload.get("transcription")

                    if not isinstance(tr, dict):
                        continue

                    text = tr.get("text", "")
                    is_final = tr.get("isFinal", False)

                    await websocket.send_json({
                        "type": "transcription",
                        "text": text,
                        "is_final": is_final
                    })

                    if enable_phishing_detection and phishing_session and is_final:
                        result = phishing_session.add_sentence(text)

                        if result.get("immediate"):
                            await websocket.send_json({
                                "type": "phishing_alert",
                                "risk_level": result["immediate"]["level"],
                            })

                except:
                    continue

        response_task = asyncio.create_task(response_handler())

        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                await audio_queue.put(msg["bytes"])

    except WebSocketDisconnect:
        pass
    finally:
        await audio_queue.put(None)

        if response_task:
            response_task.cancel()

        if grpc_client:
            await grpc_client.close()
