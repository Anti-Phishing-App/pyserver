"""음성 인식 API (CLOVA Speech)"""
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, Field
import httpx
import grpc

from app.config import CLOVA_INVOKE_URL, CLOVA_SECRET_KEY
from grpc_client.clova_grpc_client import ClovaSpeechClient
from app.services.voice_phishing_service import create_session

router = APIRouter()


# =====================================================================================
# 저장된 녹음 파일 인식 (CLOVA Speech REST)
# =====================================================================================
class TranscriptionParams(BaseModel):
    """CLOVA Speech API의 params 필드 모델"""
    language: str = Field("ko-KR", description="인식 언어 [ko-KR, en-US, ja, zh-CN, zh-TW]")
    completion: str = Field("async", description="응답 방식 [sync, async]")
    wordAlignment: bool = Field(True, description="단어 정렬 출력 여부")
    fullText: bool = Field(True, description="전체 텍스트 출력 여부")


@router.post("/api/transcribe/upload")
async def transcribe_file_upload(
    media: UploadFile = File(..., description="음성 파일 (MP3, WAV, MP4 등)"),
    language: str = Form("ko-KR", description="인식 언어"),
    completion: str = Form("async", description="응답 방식")
):
    """
    음성 파일을 CLOVA Speech API로 보내 텍스트 변환 요청 (기본 async).
    성공 시 token 반환.
    """
    if not CLOVA_INVOKE_URL or not CLOVA_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLOVA API 환경 변수가 설정되지 않았습니다.")

    headers = {"X-CLOVASPEECH-API-KEY": CLOVA_SECRET_KEY}

    callback_url = "http://13.125.25.96:8000/api/transcribe/callback"

    params_dict = {
        "language": language,
        "completion": completion,
        "callback": callback_url,
        "wordAlignment": True,
        "fullText": True,
    }
    params_json = json.dumps(params_dict, ensure_ascii=False)

    files = {
        "media": (media.filename, await media.read(), media.content_type),
        "params": (None, params_json, "application/json"),
    }

    clova_url = f"{CLOVA_INVOKE_URL}/recognizer/upload"

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        try:
            resp = await client.post(clova_url, headers=headers, files=files)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code,
                                detail=f"CLOVA API Error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"CLOVA API 요청 실패: {e}")


@router.post("/api/transcribe/callback")
async def clova_callback(request: Request):
    """
    CLOVA Speech async 결과를 수신하는 콜백 엔드포인트
    """
    try:
        payload = await request.json()
        print("🔥 [CLOVA CALLBACK RECEIVED] ====================================")
        print(payload)
        print("=================================================================")

        # 필요하면 DB 저장 or 파일 저장 가능
        # 여기서는 수신만 확인
        return {"status": "ok", "received": True}

    except Exception as e:
        print(f"[Callback Parse Error] {e}")
        raise HTTPException(500, f"Callback error: {e}")

@router.get("/api/transcribe/status/{token}")
async def transcribe_status(token: str):
    """upload API에서 받은 token으로 상태/결과 조회"""
    if not CLOVA_INVOKE_URL or not CLOVA_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLOVA API 환경 변수가 설정되지 않았습니다.")

    headers = {"X-CLOVASPEECH-API-KEY": CLOVA_SECRET_KEY}
    clova_url = f"{CLOVA_INVOKE_URL}/recognizer/{token}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        try:
            resp = await client.get(clova_url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code,
                                detail=f"CLOVA API Error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"CLOVA API 요청 실패: {e}")


# =====================================================================================
# 실시간 스트리밍 음성 인식 (WebSocket + gRPC - NestService)
# =====================================================================================
@router.websocket("/ws/transcribe/stream")
async def websocket_transcribe_stream(websocket: WebSocket, lang: str = "ko-KR", enable_phishing_detection: bool = True):
    """
    실시간 음성 인식 + 보이스피싱 탐지 WebSocket

    Args:
        lang: 언어 코드 (기본값: ko-KR)
        enable_phishing_detection: 보이스피싱 탐지 활성화 여부 (기본값: True)

    WebSocket 메시지 형식:
        - type: "transcription" - 음성 인식 결과
        - type: "phishing_alert" - 보이스피싱 탐지 알림
        - type: "error" - 에러 메시지
    """
    await websocket.accept()

    grpc_client: ClovaSpeechClient | None = None
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    response_task: asyncio.Task | None = None
    phishing_session = None

    try:
        if not CLOVA_SECRET_KEY:
            raise RuntimeError("CLOVA_SECRET_KEY 환경변수가 필요합니다.")

        # 보이스피싱 탐지 세션 초기화
        if enable_phishing_detection:
            try:
                phishing_session = create_session(window_size=5)
            except Exception as e:
                print(f"보이스피싱 탐지 초기화 실패: {e}")
                enable_phishing_detection = False

        grpc_client = ClovaSpeechClient(secret_key=CLOVA_SECRET_KEY)
        lang_short = (lang or "ko-KR").split("-")[0].lower()

        config_dict = {
            "transcription": {
                "language": lang_short
            },
            "semanticEpd": {
                "skipEmptyText": True,
                "useWordEpd": False,
                "usePeriodEpd": True,
            }
        }
        config_json = json.dumps(config_dict, ensure_ascii=False)

        async def response_handler():
            try:
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

                        if isinstance(tr, dict) and "text" in tr:
                            text = tr.get("text", "")
                            is_final = tr.get("isFinal", False)

                            # 음성 인식 결과 전송
                            await websocket.send_json({
                                "type": "transcription",
                                "text": text,
                                "is_final": is_final
                            })

                            # 보이스피싱 탐지 (최종 결과이고, 충분한 길이일 때)
                            if enable_phishing_detection and phishing_session and is_final and len(text) >= 5:
                                try:
                                    result = phishing_session.add_sentence(text)

                                    # 즉시 분석 결과 (단어 기반)
                                    if result['immediate'] and result['immediate']['level'] > 0:
                                        await websocket.send_json({
                                            "type": "phishing_alert",
                                            "alert_type": "immediate",
                                            "text": text,
                                            "risk_level": result['immediate']['level'],
                                            "risk_probability": result['immediate']['probability'],
                                            "phishing_type": result['immediate'].get('phishing_type'),
                                            "keywords": result['immediate'].get('keywords', [])
                                        })

                                    # 종합 분석 결과 (KoBERT)
                                    if result['comprehensive']:
                                        if result['comprehensive']['is_phishing']:
                                            await websocket.send_json({
                                                "type": "phishing_alert",
                                                "alert_type": "comprehensive",
                                                "is_phishing": True,
                                                "confidence": result['comprehensive']['confidence'],
                                                "analyzed_length": result['comprehensive']['analyzed_length']
                                            })

                                except Exception as e:
                                    print(f"보이스피싱 탐지 오류: {e}")

                    except Exception as e:
                        print(f"Payload parsing error: {e}")
                        await websocket.send_json({"type": "debug", "contents": contents})

            except grpc.aio.AioRpcError as e:
                msg = f"gRPC Error: {e.details()} (code: {e.code().name})"
                print(msg)
                try: await websocket.send_json({"type": "error", "message": msg})
                except Exception: pass
            except Exception as e:
                print(f"Response handler error: {e}")
                try: await websocket.send_json({"type": "error", "message": f"{e}"})
                except Exception: pass

        response_task = asyncio.create_task(response_handler())

        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                await audio_queue.put(message["bytes"])

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"WS handler error: {e}")
        try: await websocket.send_json({"type": "error", "message": str(e)})
        except Exception: pass
    finally:
        try: await audio_queue.put(None)
        except Exception: pass

        if response_task and not response_task.done():
            response_task.cancel()
            try: await response_task
            except asyncio.CancelledError: pass

        if grpc_client:
            try: await grpc_client.close()
            except Exception: pass

        if phishing_session:
            phishing_session.reset()

        print("Real-time transcription resources cleaned up.")
