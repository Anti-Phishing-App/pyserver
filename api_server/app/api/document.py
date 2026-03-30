"""수정된 문서 분석 API (api_server/app/api/document.py)"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import requests  # AI 서버에 요청을 보내기 위해 필요합니다.
from app.config import UPLOAD_DIR
from app.utils.file_handler import save_upload_file

router = APIRouter()

# AI 서버의 주소 (도커 컴포즈 서비스 이름인 ai_server를 사용합니다)
AI_SERVER_URL = "http://ai_server:8001/analyze/document"

@router.post("/process-request")
async def process_request(file: UploadFile = File(...)):
    """
    1. 파일을 API 서버에 임시 저장
    2. 저장된 파일을 AI 서버(주방)로 전송하여 분석 요청
    3. 결과를 받아서 앱에 반환
    """
    # 1. 파일 저장 (API 서버의 uploads 폴더에 기록 남기기)
    filename = save_upload_file(file)
    image_path = UPLOAD_DIR / filename

    # 2. AI 서버로 파일 전달하기
    try:
        # 파일을 다시 열어서 AI 서버로 쏩니다.
        with open(image_path, "rb") as f:
            files = {"file": (filename, f, file.content_type)}
            response = requests.post(AI_SERVER_URL, files=files, timeout=60) # 분석이 기니까 타임아웃 넉넉히
        
        # AI 서버가 에러를 뱉었는지 확인
        response.raise_for_status()
        result = response.json()

        # 3. 결과 반환
        return {
            "filename": filename,
            "url": f"/uploads/{filename}",
            **result
        }

    except requests.exceptions.RequestException as e:
        # AI 서버가 죽었거나 연결이 안 될 때 에러 처리
        raise HTTPException(status_code=500, detail=f"AI 서버 연결 실패: {str(e)}")