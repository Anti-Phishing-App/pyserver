import os
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

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
