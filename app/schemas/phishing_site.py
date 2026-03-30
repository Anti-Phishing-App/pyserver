"""
피싱 사이트 탐지 API 스키마

이 모듈은 피싱 사이트 탐지 API의 요청/응답 스키마를 정의합니다.

스키마 종류:
    - URLAnalysisRequest: URL 분석 요청
    - ImmediateResult: URL 기반 즉시 분석 결과
    - ComprehensiveResult: ML 모델 기반 종합 분석 결과
    - AnalysisResponse: 전체 분석 응답
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class URLAnalysisRequest(BaseModel):
    """URL 기반 피싱 사이트 분석 요청"""
    url: str = Field(..., min_length=10, description="분석할 URL (최소 10자)")
    method: str = Field("hybrid", description="분석 방법 [immediate, comprehensive, hybrid]")


class ImmediateResult(BaseModel):
    """즉시 분석 결과 (URL 기반)"""
    level: int = Field(..., description="위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)")
    score: float = Field(..., description="위험 점수 (0-100)")
    reasons: List[str] = Field(default_factory=list, description="위험 요인 목록")
    method: str = Field("url_based", description="분석 방법")
    domain: Optional[str] = Field(None, description="도메인명")


class ComprehensiveResult(BaseModel):
    """종합 분석 결과 (ML + PhishTank DB)"""
    is_phishing: bool = Field(..., description="피싱 사이트 여부")
    confidence: float = Field(..., description="예측 신뢰도 (0.0-1.0)")
    source: str = Field(..., description="탐지 소스 (phishtank, ml_model, none, error)")
    method: str = Field("comprehensive", description="분석 방법")
    analyzed_url: str = Field(..., description="분석한 URL")
    error: Optional[str] = Field(None, description="에러 메시지 (있을 경우)")


class AnalysisResponse(BaseModel):
    """피싱 사이트 분석 응답"""
    immediate: Optional[ImmediateResult] = None
    comprehensive: Optional[ComprehensiveResult] = None
    warning_message: Optional[str] = None
