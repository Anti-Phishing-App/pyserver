import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

# 환경 변수 로드
load_dotenv(BASE_DIR / ".env")

# 업로드 설정
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# CLOVA Speech API 설정
CLOVA_INVOKE_URL = os.getenv("CLOVA_INVOKE_URL")
CLOVA_SECRET_KEY = os.getenv("CLOVA_SECRET_KEY")
CLOVA_CLIENT_ID = os.getenv("CLOVA_CLIENT_ID")
CLOVA_CLIENT_SECRET = os.getenv("CLOVA_CLIENT_SECRET")

# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-please-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/users.db")
