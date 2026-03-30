import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os

from app.services.document_service import analyze_document
from app.api import voice_phishing, phishing_site, sms, transcribe, transcribe_stream

# 로깅 설정 (AI 서버용)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_server")

app = FastAPI(title="AI Analysis Worker Server", version="1.0.0")

# 분석용 임시 디렉토리
TEMP_DIR = "temp_analysis"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/analyze/document")
def analyze_doc_task(file: UploadFile = File(...)):
    """API 서버로부터 파일을 전달받아 AI 모델로 분석을 수행합니다."""
    file_path = os.path.join(TEMP_DIR, file.filename)
    try:
        # 1. 파일 임시 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. 🔥 AI 모델 실행 (진짜 분석 작업)
        logger.info(f"Starting analysis for: {file.filename}")
        result = analyze_document(file_path)
        
        return result
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# AI 연산 라우터는 AI 서버에서 직접 제공
app.include_router(transcribe.router, tags=["Transcribe"])
app.include_router(transcribe_stream.router)
app.include_router(voice_phishing.router, tags=["Voice Phishing Detection"])
app.include_router(phishing_site.router, tags=["Phishing Site Detection"])
app.include_router(sms.router, tags=["SMS Phishing Detection"])

@app.get("/healthz")
def healthz():
    """AI 서버 생존 확인용"""
    return {"status": "ok", "service": "ai_server"}