"""
SMS 피싱 탐지 API 스키마

이 모듈은 SMS 피싱 탐지 API의 요청/응답 스키마를 정의합니다.

스키마 종류:
    - SmsDetectRequest: SMS 피싱 탐지 요청
    - TextAnalysisResult: 텍스트 분석 결과
    - UrlAnalysisResult: URL 분석 결과
    - SmsDetectResponse: SMS 피싱 탐지 응답
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class SmsDetectRequest(BaseModel):
    """SMS 피싱 탐지 요청"""
    sender_hash: str = Field(..., description="발신자 번호 해시값 (SHA-256)")
    urls: List[str] = Field(default_factory=list, description="SMS에서 추출된 URL 목록")
    texts: List[str] = Field(..., description="SMS 텍스트 문장 목록")
    received_at: int = Field(..., description="수신 시간 (밀리초 단위 타임스탬프)")


class TextAnalysisResult(BaseModel):
    """텍스트 분석 결과"""
    risk_level: int = Field(..., description="위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)")
    risk_probability: float = Field(..., description="위험 확률 (0-100)")
    phishing_type: Optional[str] = Field(None, description="범죄 유형 (대출사기형 or 수사기관사칭형)")
    keywords: List[str] = Field(default_factory=list, description="탐지된 위험 단어")
    is_phishing_kobert: Optional[bool] = Field(None, description="KoBERT 분석 결과 - 피싱 여부")
    kobert_confidence: Optional[float] = Field(None, description="KoBERT 신뢰도 (0.0-1.0)")


class UrlAnalysisResult(BaseModel):
    """URL 분석 결과"""
    url: str = Field(..., description="분석한 URL")
    risk_level: int = Field(..., description="위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)")
    risk_probability: float = Field(..., description="위험 확률 (0-100)")
    suspicious_features: List[str] = Field(default_factory=list, description="의심스러운 URL 특징")
    is_phishing_ml: Optional[bool] = Field(None, description="ML 모델 분석 결과 - 피싱 여부")
    ml_confidence: Optional[float] = Field(None, description="ML 모델 신뢰도 (0.0-1.0)")
    phishtank_matched: Optional[bool] = Field(None, description="PhishTank DB 매칭 여부")


class SmsDetectResponse(BaseModel):
    """SMS 피싱 탐지 응답"""
    phishing_score: float = Field(..., description="종합 피싱 점수 (0-100)")
    risk_level: int = Field(..., description="종합 위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)")
    is_phishing: bool = Field(..., description="피싱 여부 (phishing_score >= 50)")
    warning_message: str = Field(..., description="경고 메시지")

    # 텍스트 분석 결과
    text_analysis: Optional[TextAnalysisResult] = Field(None, description="텍스트 분석 결과")

    # URL 분석 결과
    url_analysis: List[UrlAnalysisResult] = Field(default_factory=list, description="URL별 분석 결과")

    # 기존 호환성을 위한 필드
    keywords_found: List[str] = Field(default_factory=list, description="탐지된 키워드 전체 목록")
    url_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="URL별 결과 맵")
