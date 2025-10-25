"""문서 분석 API"""
from fastapi import APIRouter, UploadFile, File

from app.config import UPLOAD_DIR
from app.utils.file_handler import save_upload_file
from app.services.document_service import analyze_document

router = APIRouter()


@router.post("/process-request")
async def process_request(file: UploadFile = File(...)):
    """
    업로드된 이미지를 기반으로 모든 분석 기능 수행
    (직인, OCR, 키워드, 레이아웃, 위험도)
    """
    # 파일 저장
    filename = save_upload_file(file)
    image_path = UPLOAD_DIR / filename

    # 문서 분석
    result = analyze_document(image_path)

    return {
        "filename": filename,
        "url": f"/uploads/{filename}",
        **result
    }
