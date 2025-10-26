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

        # 가중치 부여: 직인 50%, 키워드 50%
        final_risk = round((stamp_score * 0.5) + (keyword_score * 0.5), 2)

        return {
            "stamp": stamp_result,
            "ocr": ocr_result,
            "keyword": keyword_result,
            "layout": layout_result,
            "final_risk": final_risk
        }

    except OCRError as e:
        raise HTTPException(status_code=500, detail=f"OCR 처리 실패: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알 수 없는 서버 오류: {e}")
