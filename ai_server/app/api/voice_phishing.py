"""
보이스피싱 탐지 API 라우터

이 모듈은 보이스피싱 탐지 관련 REST API 엔드포인트를 제공합니다.

주요 기능:
    1. 텍스트 기반 분석 (/analyze)
       - 입력된 텍스트의 보이스피싱 여부 분석
       - 하이브리드 탐지: 단어 기반 + KoBERT 딥러닝

    2. 음성 파일 분석 (/analyze-audio)
       - 음성 파일 → STT → 보이스피싱 탐지 (원스톱)
       - CLOVA Speech API와 통합

    3. 서비스 상태 확인 (/health)
       - 모델 로드 상태 및 서비스 가용성 체크

분석 방법:
    - immediate: 단어 기반 즉시 분석 (빠름, 실시간 적합)
    - comprehensive: KoBERT 종합 분석 (정확함, 누적 분석 적합)
    - hybrid: 두 방법 모두 실행 (기본값, 추천)

실시간 스트리밍 탐지는 /ws/transcribe/stream (transcribe.py)에서 처리됩니다.
"""
import json
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import httpx

from app.schemas.voice_phishing import (
    TextAnalysisRequest,
    AnalysisResponse,
    ImmediateResult,
    ComprehensiveResult,
)
from app.services.voice_phishing_service import get_detector
from app.config import CLOVA_INVOKE_URL, CLOVA_SECRET_KEY

router = APIRouter(prefix="/api/voice-phishing")


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    텍스트 기반 보이스피싱 분석

    3가지 분석 방법 지원:
    - immediate: 단어 기반 즉시 분석 (빠름, 실시간 적합)
    - comprehensive: KoBERT 기반 종합 분석 (정확함, 누적 분석 적합)
    - hybrid: 두 방법 모두 실행 (기본값)

    Args:
        request: TextAnalysisRequest
            - text: 분석할 텍스트 (최소 10자)
            - method: 분석 방법 (immediate, comprehensive, hybrid)

    Returns:
        AnalysisResponse:
            - immediate: 단어 기반 즉시 분석 결과
            - comprehensive: KoBERT 종합 분석 결과
            - warning_message: 경고 메시지

    Example:
        ```json
        {
            "text": "대출 상담 도와드리겠습니다. 계좌번호 알려주세요.",
            "method": "hybrid"
        }
        ```
    """
    try:
        detector = get_detector()

        immediate_result = None
        comprehensive_result = None
        warning_message = None

        # Immediate 분석 (단어 기반)
        if request.method in ["immediate", "hybrid"]:
            result = detector.detect_immediate(request.text)
            immediate_result = ImmediateResult(**result)

            # 위험도에 따른 경고 메시지
            if immediate_result.level == 3:
                warning_message = "⚠️ 위험: 보이스피싱일 가능성이 매우 높습니다!"
            elif immediate_result.level == 2:
                warning_message = "⚠️ 경고: 의심스러운 단어가 감지되었습니다."
            elif immediate_result.level == 1:
                warning_message = "ℹ️ 주의: 일부 단어에 주의가 필요합니다."

        # Comprehensive 분석 (KoBERT)
        if request.method in ["comprehensive", "hybrid"]:
            result = detector.detect_comprehensive(request.text)
            comprehensive_result = ComprehensiveResult(**result)

            # KoBERT 결과에 따른 경고 메시지
            if comprehensive_result.is_phishing:
                confidence_pct = comprehensive_result.confidence * 100
                warning_message = f"🚨 보이스피싱 탐지! (신뢰도: {confidence_pct:.1f}%)"

        return AnalysisResponse(
            immediate=immediate_result,
            comprehensive=comprehensive_result,
            warning_message=warning_message
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"모델 파일을 찾을 수 없습니다: {e}"
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"필요한 라이브러리가 설치되지 않았습니다: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"보이스피싱 분석 중 오류 발생: {e}"
        )


@router.post("/analyze-audio")
async def analyze_audio_file(
    media: UploadFile = File(..., description="음성 파일 (MP3, WAV, MP4 등)"),
    language: str = Form("ko-KR", description="인식 언어"),
    analysis_method: str = Form("hybrid", description="분석 방법 [항상 hybrid 처리]")
):
    """
    통화 녹음 파일 보이스피싱 탐지 (STT + 분석)

    음성 파일을 받아서:
    1. CLOVA Speech API로 텍스트 변환 (동기 방식)
    2. 변환된 텍스트로 보이스피싱 탐지
    3. 결과 반환

    Args:
        media: 음성 파일
        language: 인식 언어 (기본값: ko-KR)
        analysis_method: 분석 방법 (immediate, comprehensive, hybrid)

    Returns:
        dict:
            - transcription: STT 결과 (텍스트)
            - phishing_analysis: 보이스피싱 분석 결과

    Example:
        curl -X POST "http://localhost:8000/api/voice-phishing/analyze-audio" \\
             -F "media=@recording.mp3" \\
             -F "analysis_method=hybrid"
    """
    if not CLOVA_INVOKE_URL or not CLOVA_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLOVA API 환경 변수가 설정되지 않았습니다.")

    try:
        # Step 1: STT (동기 방식으로 즉시 결과 반환)
        headers = {"X-CLOVASPEECH-API-KEY": CLOVA_SECRET_KEY}

        params_dict = {
            "language": language,
            "completion": "sync",  # 동기 방식
            "wordAlignment": True,
            "fullText": True,
        }
        params_json = json.dumps(params_dict, ensure_ascii=False)

        # 파일 읽기
        file_content = await media.read()

        files = {
            "media": (media.filename, file_content, media.content_type),
            "params": (None, params_json, "application/json"),
        }

        clova_url = f"{CLOVA_INVOKE_URL}/recognizer/upload"

        # STT 요청
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            try:
                resp = await client.post(clova_url, headers=headers, files=files)
                resp.raise_for_status()
                stt_result = resp.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"CLOVA API Error: {e.response.text}"
                )
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"CLOVA API 요청 실패: {e}")

        # Step 2: 텍스트 추출
        text = stt_result.get("text", "")
        if not text or len(text) < 10:
            return {
                "transcription": {
                    "text": text,
                    "stt_result": stt_result
                },
                "phishing_analysis": {
                    "error": "텍스트가 너무 짧아서 분석할 수 없습니다 (최소 10자 필요)"
                }
            }

        # Step 3: 보이스피싱 탐지
        detector = get_detector()

        immediate_result = None
        comprehensive_result = None
        warning_message = None

        # 음성 분석은 항상 하이브리드 실행
        result = detector.detect_immediate(text)
        immediate_result = ImmediateResult(**result)

        if immediate_result.level == 3:
            warning_message = "⚠️ 위험: 보이스피싱일 가능성이 매우 높습니다!"
        elif immediate_result.level == 2:
            warning_message = "⚠️ 경고: 의심스러운 단어가 감지되었습니다."
        elif immediate_result.level == 1:
            warning_message = "ℹ️ 주의: 일부 단어에 주의가 필요합니다."

        comprehensive = detector.detect_comprehensive(text)
        comprehensive_result = ComprehensiveResult(**comprehensive)
        if comprehensive_result.is_phishing:
            confidence_pct = comprehensive_result.confidence * 100
            warning_message = f"🚨 보이스피싱 탐지! (신뢰도: {confidence_pct:.1f}%)"

        return {
            "transcription": {
                "text": text,
                "confidence": stt_result.get("confidence"),
                "speaker": stt_result.get("speaker"),
                "stt_result": stt_result
            },
            "phishing_analysis": {
                "immediate": immediate_result.dict() if immediate_result else None,
                "comprehensive": comprehensive_result.dict() if comprehensive_result else None,
                "warning_message": warning_message
            }
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"모델 파일을 찾을 수 없습니다: {e}"
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"필요한 라이브러리가 설치되지 않았습니다: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"보이스피싱 분석 중 오류 발생: {e}"
        )


@router.get("/health")
async def health_check():
    """
    보이스피싱 탐지 서비스 상태 확인

    Returns:
        dict: 서비스 상태 정보
    """
    try:
        detector = get_detector()
        return {
            "status": "ok",
            "model_loaded": detector.model is not None,
            "device": str(detector.device),
            "message": "보이스피싱 탐지 서비스가 정상 작동 중입니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"서비스 상태 확인 실패: {e}"
        )
