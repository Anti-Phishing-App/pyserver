"""무거운 AI 분석 전용 서버 (ai_server/app/main.py)"""
from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os

# AI 주방으로 무사히 이사 온 진짜 분석 로직들을 불러옵니다!
from app.services.document_service import analyze_document

# FastAPI 앱 초기화 (AI 전용, 아주 가볍게 만듭니다)
app = FastAPI(title="Phishing AI Analysis Server", version="1.0.0")

# 카운터에서 넘어온 파일을 잠시 담아둘 임시 폴더
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.get("/healthz")
def healthz():
    """AI 서버가 살아있는지 확인하는 용도"""
    return {"status": "ok", "service": "ai_server"}

# 🚨 반드시 async def가 아닌 def로 작성합니다! (CPU 연산 방해 금지)
@app.post("/analyze")
def analyze_doc(file: UploadFile = File(...)):
    """
    카운터(API)에서 넘어온 파일을 받아서 AI 분석만 수행하고 결과를 돌려줍니다.
    """
    temp_path = os.path.join(TEMP_DIR, file.filename)
    
    try:
        # 1. 파일 임시 저장
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. 🔥 AI 문서 분석 시작 (여기서 3~4초 걸립니다)
        result = analyze_document(temp_path)

        # 3. 분석이 끝났으니 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # 4. 분석 결과 반환
        return result

    except Exception as e:
        # 파일 지우기 (에러 났을 때도 쓰레기가 남지 않게)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"AI 분석 중 오류 발생: {str(e)}")