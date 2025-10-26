"""FastAPI 메인 애플리케이션"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR
from app.api import upload, transcribe, document, auth, user
from app.core.database import init_db

# FastAPI 앱 초기화
app = FastAPI(title="PyServer API", version="1.0.0")


# 애플리케이션 시작 시 DB 초기화
@app.on_event("startup")
def on_startup():
    """애플리케이션 시작 시 데이터베이스 초기화"""
    init_db()


# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="."), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# API 라우터 등록
app.include_router(auth.router, tags=["Authentication"])
app.include_router(user.router, tags=["User Management"])
app.include_router(upload.router, tags=["Upload"])
app.include_router(transcribe.router, tags=["Transcribe"])
app.include_router(document.router, tags=["Document"])


# =========================
# 루트 및 기본 엔드포인트
# =========================
@app.get("/")
def read_root():
    """
    루트 접근 시 index.html 반환
    """
    index_path = Path("index.html")
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    fallback = """
    <!doctype html>
    <html lang="ko"><head><meta charset="utf-8">
    <title>Server Running</title></head>
    <body style="font-family:sans-serif">
      <h1>FastAPI 서버가 실행 중입니다.</h1>
      <p><code>index.html</code> 파일이 루트에 없어서 기본 페이지를 표시합니다.</p>
      <ul>
        <li><a href="/docs">/docs</a> (Swagger UI)</li>
        <li><a href="/redoc">/redoc</a> (ReDoc)</li>
      </ul>
    </body></html>
    """
    return HTMLResponse(fallback)


@app.get("/favicon.ico")
def favicon():
    """favicon 404 소음 방지"""
    fav = Path("favicon.ico")
    if fav.exists():
        return FileResponse(str(fav))
    return HTMLResponse(status_code=204, content="")


@app.get("/healthz")
def healthz():
    """Health check"""
    return {"status": "ok"}
