"""카운터 전용 FastAPI 메인 애플리케이션 (api_server/app/main.py)"""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR
# API 서버는 인증/유저/업로드/게이트웨이 성격의 라우터만 포함합니다.
from app.api import upload, document, auth, user
from app.core.database import init_db
from app.api.logs import router as logs_router

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# FastAPI 앱 초기화
app = FastAPI(title="Phishing Prevention API Server", version="1.0.0")

# 애플리케이션 시작 시 DB 초기화 (카운터가 DB를 관리함)
@app.on_event("startup")
def on_startup():
    init_db()

# 정적 파일 및 업로드 파일 서빙 (사용자에게 직접 보여주는 역할)
app.mount("/static", StaticFiles(directory="."), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# API 라우터 등록
app.include_router(auth.router, tags=["Authentication"])      # 로그인 담당
app.include_router(user.router, tags=["User Management"])    # 유저 담당
app.include_router(upload.router, tags=["Upload"])           # 파일 받기 담당
app.include_router(document.router, tags=["Document"])       # 분석 요청 전달 담당
app.include_router(logs_router)

@app.get("/")
def read_root():
    index_path = Path("index.html")
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>API Server Running</h1>")

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "api_server"}