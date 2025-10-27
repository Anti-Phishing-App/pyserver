"""
피싱 사이트 탐지 API 라우터

이 모듈은 피싱 사이트 탐지 관련 REST API 엔드포인트를 제공합니다.

주요 기능:
    1. URL 기반 분석 (/analyze)
       - 입력된 URL의 피싱 사이트 여부 분석
       - 하이브리드 탐지: URL 기반 + ML 모델 + PhishTank DB

    2. 서비스 상태 확인 (/health)
       - 모델 로드 상태 및 서비스 가용성 체크

분석 방법:
    - immediate: URL 기반 즉시 분석 (빠름, 크롤링 없음)
    - comprehensive: ML 모델 + PhishTank DB (정확함, HTML 크롤링 포함)
    - hybrid: 두 방법 모두 실행 (기본값, 추천)
"""
from fastapi import APIRouter, HTTPException

from app.schemas.phishing_site import (
    URLAnalysisRequest,
    AnalysisResponse,
    ImmediateResult,
    ComprehensiveResult,
)
from app.services.phishing_site_detector import get_detector

router = APIRouter(prefix="/api/phishing-site")


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_url(request: URLAnalysisRequest):
    """
    URL 기반 피싱 사이트 분석

    3가지 분석 방법 지원:
    - immediate: URL 기반 즉시 분석 (빠름, 크롤링 없음)
    - comprehensive: ML 모델 + PhishTank DB (정확함, HTML 크롤링 포함)
    - hybrid: 두 방법 모두 실행 (기본값)

    Args:
        request: URLAnalysisRequest
            - url: 분석할 URL (최소 10자)
            - method: 분석 방법 (immediate, comprehensive, hybrid)

    Returns:
        AnalysisResponse:
            - immediate: URL 기반 즉시 분석 결과
            - comprehensive: ML 모델 종합 분석 결과
            - warning_message: 경고 메시지

    Example:
        ```json
        {
            "url": "http://paypal-secure-login.tk/",
            "method": "hybrid"
        }
        ```
    """
    try:
        detector = get_detector()

        immediate_result = None
        comprehensive_result = None
        warning_message = None

        # Immediate 분석 (URL 기반)
        if request.method in ["immediate", "hybrid"]:
            result = detector.detect_immediate(request.url)
            immediate_result = ImmediateResult(**result)

            # 위험도에 따른 경고 메시지
            if immediate_result.level == 3:
                warning_message = "⚠️ 위험: 피싱 사이트일 가능성이 매우 높습니다!"
            elif immediate_result.level == 2:
                warning_message = "⚠️ 경고: 의심스러운 URL 특징이 감지되었습니다."
            elif immediate_result.level == 1:
                warning_message = "ℹ️ 주의: 일부 URL 특징에 주의가 필요합니다."

        # Comprehensive 분석 (ML + PhishTank DB)
        if request.method in ["comprehensive", "hybrid"]:
            result = detector.detect_comprehensive(request.url)
            comprehensive_result = ComprehensiveResult(**result)

            # ML 결과에 따른 경고 메시지
            if comprehensive_result.is_phishing:
                confidence_pct = comprehensive_result.confidence * 100
                source_str = "PhishTank DB" if comprehensive_result.source == "phishtank" else "ML 모델"
                warning_message = f"🚨 피싱 사이트 탐지! (신뢰도: {confidence_pct:.1f}%, 소스: {source_str})"

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
            detail=f"피싱 사이트 분석 중 오류 발생: {e}"
        )


@router.get("/health")
async def health_check():
    """
    피싱 사이트 탐지 서비스 상태 확인

    Returns:
        dict: 서비스 상태 정보
    """
    try:
        detector = get_detector()
        return {
            "status": "ok",
            "model_loaded": detector.model is not None,
            "phishtank_db_loaded": len(detector.phishtank_db) > 0,
            "phishtank_db_size": len(detector.phishtank_db),
            "message": "피싱 사이트 탐지 서비스가 정상 작동 중입니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"서비스 상태 확인 실패: {e}"
        )
