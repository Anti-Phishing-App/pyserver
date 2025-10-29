"""문서 분석 서비스"""
from pathlib import Path
from fastapi import HTTPException

from app.ml.predictors.ocr_predictor import run_ocr, OCRError
from app.ml.predictors.keyword_predictor import detect_keywords
from app.ml.predictors.layout_predictor import analyze_document_font
from app.ml.predictors.stamp_predictor import run_stamp_detection


def analyze_document(image_path: Path) -> dict:
    """
    문서 이미지 전체 분석 (OCR, 키워드, 레이아웃, 직인, 위험도)

    Args:
        image_path: 분석할 이미지 경로

    Returns:
        분석 결과 딕셔너리
    """
    try:
        # 각 기능별 분석 호출
        stamp_result = run_stamp_detection(str(image_path))
        ocr_result = run_ocr(str(image_path))
        keyword_result = detect_keywords(ocr_result)
        layout_result = analyze_document_font(ocr_result)

        # 간이 위험도 계산
        stamp_score = stamp_result.get("score", 0) or 0.0
        keyword_score = keyword_result.get("total_score", 0) or 0.0
        layout_score = layout_result.get("score", 0) or 0.0

        # 가중치 부여: 직인 30%, 키워드 50%, 레이아웃 20%
        # TODO : 기능 실행 후 상세 퍼센트 조정
        final_risk = round((stamp_score * 0.3) + (keyword_score * 0.5) + (layout_score * 0.2), 2) 

        # 각 분석 함수의 전체 결과 딕셔너리를 그대로 반환받아서 합친 형태로 기존 함수들이 반환하던 상세 정보(boxes, details, risk_level 등)는 모두 그대로 유지됨
        # 점수만 사용 원할 경우 final_risk 만 사용하면 되는 그런 형태임!!!
        return {
            "stamp": stamp_result,
            "keyword": keyword_result,
            "layout": layout_result,
            "final_risk": final_risk
        }

    except OCRError as e:
        raise HTTPException(status_code=500, detail=f"OCR 처리 실패: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알 수 없는 서버 오류: {e}")
