"""보이스피싱 탐지 스키마"""
from pydantic import BaseModel, Field
from typing import Optional, List


class TextAnalysisRequest(BaseModel):
    """텍스트 기반 보이스피싱 분석 요청"""
    text: str = Field(..., min_length=10, description="분석할 텍스트 (최소 10자)")
    method: str = Field("comprehensive", description="분석 방법 [immediate, comprehensive, hybrid]")


class ImmediateResult(BaseModel):
    """즉시 분석 결과 (단어 기반)"""
    level: int = Field(..., description="위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)")
    probability: float = Field(..., description="위험 확률 (0-100)")
    phishing_type: Optional[str] = Field(None, description="범죄 유형 (대출사기형 or 수사기관사칭형)")
    keywords: List[str] = Field(default_factory=list, description="탐지된 위험 단어")
    method: str = Field("word_based", description="분석 방법")


class ComprehensiveResult(BaseModel):
    """종합 분석 결과 (KoBERT)"""
    is_phishing: bool = Field(..., description="보이스피싱 여부")
    confidence: float = Field(..., description="예측 신뢰도 (0.0-1.0)")
    method: str = Field("kobert", description="분석 방법")
    analyzed_length: int = Field(..., description="분석한 텍스트 길이")


class AnalysisResponse(BaseModel):
    """보이스피싱 분석 응답"""
    immediate: Optional[ImmediateResult] = None
    comprehensive: Optional[ComprehensiveResult] = None
    warning_message: Optional[str] = None


class StreamAnalysisMessage(BaseModel):
    """실시간 스트리밍 분석 메시지"""
    type: str = Field(..., description="메시지 타입 [transcription, phishing_alert, error]")
    text: Optional[str] = Field(None, description="인식된 텍스트")
    is_final: Optional[bool] = Field(None, description="최종 결과 여부")

    # 보이스피싱 탐지 결과
    phishing_detected: Optional[bool] = None
    risk_level: Optional[int] = None
    risk_probability: Optional[float] = None
    phishing_type: Optional[str] = None
    keywords: Optional[List[str]] = None

    # KoBERT 종합 분석
    kobert_is_phishing: Optional[bool] = None
    kobert_confidence: Optional[float] = None
