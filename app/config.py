"""
애플리케이션 설정

환경변수를 로드하고 애플리케이션 전역에서 사용할 설정값을 정의합니다.
.env 파일에서 환경변수를 읽어오며, 없을 경우 기본값을 사용합니다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리 경로
# __file__: 현재 파일(config.py)의 경로
# .parent.parent: app/config.py -> app/ -> pyserver/
BASE_DIR = Path(__file__).resolve().parent.parent

# .env 파일에서 환경변수 로드
# .env 파일이 없어도 에러가 발생하지 않습니다
load_dotenv(BASE_DIR / ".env")

# ==========================================
# 파일 업로드 설정
# ==========================================
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 디렉토리가 없으면 자동 생성
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))  # 최대 업로드 파일 크기 (MB)
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024  # MB를 바이트로 변환

# ==========================================
# CLOVA Speech API 설정 (STT)
# ==========================================
# 네이버 클로바 음성인식 API 사용을 위한 인증 정보
CLOVA_INVOKE_URL = os.getenv("CLOVA_INVOKE_URL")  # gRPC 서버 URL
CLOVA_SECRET_KEY = os.getenv("CLOVA_SECRET_KEY")  # API 시크릿 키
CLOVA_CLIENT_ID = os.getenv("CLOVA_CLIENT_ID")  # 클라이언트 ID
CLOVA_CLIENT_SECRET = os.getenv("CLOVA_CLIENT_SECRET")  # 클라이언트 시크릿

# ==========================================
# JWT 인증 설정
# ==========================================
# JWT_SECRET_KEY: 토큰 서명에 사용되는 비밀키 (반드시 .env에서 설정 필요!)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-please-change-in-production")

# JWT_ALGORITHM: JWT 서명 알고리즘 (HS256, HS512 등)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# JWT_ACCESS_TOKEN_EXPIRE_MINUTES: 액세스 토큰 유효 시간 (분)
# 짧게 설정하여 보안 강화 (기본값: 30분)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# JWT_REFRESH_TOKEN_EXPIRE_DAYS: 리프레시 토큰 유효 시간 (일)
# 액세스 토큰 갱신을 위해 사용 (기본값: 7일)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ==========================================
# 데이터베이스 설정
# ==========================================
# SQLite 데이터베이스 URL
# 형식: sqlite:///경로/파일명.db
# PostgreSQL 사용 시: postgresql://user:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/users.db")


# ==========================================
# 소셜 로그인 설정 (카카오)
# ==========================================
# 카카오 개발자 센터에서 발급받은 REST API 키
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "your-kakao-client-id")
# 카카오 로그인 콜백 URL (카카오 개발자 센터에 등록된 리다이렉트 URI)
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8000/auth/kakao/callback")
