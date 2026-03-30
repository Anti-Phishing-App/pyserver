"""문서 분석 API (카운터 알바생 역할)"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import httpx  # AI 서버랑 통신하기 위한 전화기 역할!
import os

from app.config import UPLOAD_DIR
from app.utils.file_handler import save_upload_file
# 🚨 주의: AI 분석 로직은 주방(AI 서버)으로 이사 갔으므로 여기서 import 하지 않습니다!
# from app.services.document_service import analyze_document 

router = APIRouter()

# docker-compose.yml에서 설정한 AI 주방 주소를 가져옵니다.
AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://ai:8000")

@router.post("/process-request")
async def process_request(file: UploadFile = File(...)):
    """
    [변경됨] 파일만 저장하고, 무거운 분석은 AI 컨테이너로 토스합니다!
    """
    # 1. 파일 저장 (프론트엔드에서 사진을 봐야 하니 저장은 카운터에서 그대로 합니다)
    filename = save_upload_file(file)
    image_path = UPLOAD_DIR / filename

    # 2. AI 주방(서버)으로 "이 문서 분석해 줘!" 하고 요청 보내기 (비동기 통신)
    try:
        # 방금 저장한 파일을 다시 읽어서 AI 서버로 보낼 준비를 합니다.
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        # AI 분석이 3~4초 걸리니까, 전화가 끊기지 않게 30초 정도 넉넉히 기다려줍니다.
        timeout_setting = httpx.Timeout(30.0)
        
        # async with를 쓰면, AI 서버가 분석하는 동안 카운터 알바생은 다른 손님(로그인)을 받을 수 있습니다! 🚀
        async with httpx.AsyncClient(timeout=timeout_setting) as client:
            files_to_send = {"file": (filename, file_bytes, file.content_type)}
            
            # AI 서버의 /analyze 주소로 파일을 던집니다.
            response = await client.post(f"{AI_SERVER_URL}/analyze", files=files_to_send)
            response.raise_for_status() # 에러가 났는지 확인
            
            # AI 서버가 고생해서 분석한 결과물(딕셔너리)을 받아옵니다.
            ai_result = response.json() 

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 서버 분석 중 오류가 발생했습니다: {str(e)}")

    # 3. 앱에서 받아올 return 값 구조 (기존 프론트엔드 코드를 안 고쳐도 되게 똑같이 맞춰줍니다!)
    return {
        "filename": filename,
        "url": f"/uploads/{filename}",
        **ai_result
    }