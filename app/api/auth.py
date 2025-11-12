"""
Authentication API endpoints

사용자 인증 관련 API 엔드포인트를 정의합니다.
- 회원가입: 새로운 사용자 계정 생성
- 로그인: JWT 토큰 발급
- 로그아웃: 클라이언트 측 토큰 삭제 안내
- 토큰 갱신: 리프레시 토큰으로 새 액세스 토큰 발급
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest
)
from app.schemas.user import UserResponse, MessageResponse
from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter(prefix="/auth")


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    회원가입

    새로운 사용자 계정을 생성합니다.

    Args:
        request: 회원가입 요청 데이터 (username, email, password 등)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        UserResponse: 생성된 사용자 정보 (비밀번호 제외)

    Raises:
        HTTPException 400: 이미 사용 중인 username 또는 email

    Example:
        ```bash
        curl -X POST "http://localhost:8000/auth/signup" \\
             -H "Content-Type: application/json" \\
             -d '{
               "username": "john_doe",
               "email": "john@example.com",
               "password": "securepass123!",
               "full_name": "John Doe"
             }'
        ```
    """
    # 중복 체크 - username
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # 중복 체크 - email
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 새 사용자 생성
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        phone=request.phone,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    로그인

    사용자 인증 후 액세스 토큰과 리프레시 토큰을 발급합니다.
    """
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 토큰 생성
    access_token = create_access_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    refresh_token = create_refresh_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    토큰 갱신

    리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급합니다.
    """
    # 리프레시 토큰 검증
    payload = decode_token(request.refresh_token, JWT_SECRET_KEY, JWT_ALGORITHM)

    # 토큰 타입 확인
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # 사용자 존재 확인
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # 새 토큰 발급
    new_access_token = create_access_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    new_refresh_token = create_refresh_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    로그아웃

    클라이언트 측에서 토큰을 삭제하도록 안내합니다.
    (서버는 stateless이므로 클라이언트가 토큰을 삭제하면 됩니다)
    """
    return {"message": "Successfully logged out. Please delete the token on client side."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보 조회
    """
    return current_user


# ==========================================
# 카카오 소셜 로그인
# ==========================================
import httpx
from fastapi.responses import RedirectResponse
from app.config import KAKAO_CLIENT_ID, KAKAO_REDIRECT_URI

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/kakao/login", tags=["Authentication"])
def kakao_login():
    """
    카카오 로그인 페이지로 리디렉션
    """
    redirect_url = (
        f"{KAKAO_AUTH_URL}?client_id={KAKAO_CLIENT_ID}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}&response_type=code&scope=account_email"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/kakao/callback", response_model=TokenResponse, tags=["Authentication"])
async def kakao_callback(code: str, db: Session = Depends(get_db)):
    """
    카카오 로그인 콜백 처리

    카카오로부터 받은 인증 코드로 토큰을 받고, 사용자 정보를 조회하여
    - 기존 사용자인 경우: 로그인 처리 후 JWT 토큰 발급
    - 신규 사용자인 경우: 회원가입 후 JWT 토큰 발급
    """
    # 1. 인증 코드로 액세스 토큰 받기
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    async with httpx.AsyncClient() as client:
        token_response = await client.post(KAKAO_TOKEN_URL, data=token_data)
        token_response.raise_for_status()
        kakao_token = token_response.json()

    # 2. 액세스 토큰으로 사용자 정보 받기
    headers = {"Authorization": f"Bearer {kakao_token['access_token']}"}
    async with httpx.AsyncClient() as client:
        user_info_response = await client.get(KAKAO_USER_INFO_URL, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

    social_id = str(user_info["id"])
    email = user_info["kakao_account"]["email"]
    nickname = user_info["properties"]["nickname"]

    # 3. 사용자 정보로 DB 조회 및 생성
    user = db.query(User).filter(User.social_id == social_id, User.provider == "kakao").first()

    if not user:
        # 이메일로 기존 사용자 확인
        user = db.query(User).filter(User.email == email).first()
        if user:
            # 기존 계정에 소셜 정보 연동
            user.provider = "kakao"
            user.social_id = social_id
            db.commit()
        else:
            # 신규 사용자 생성
            new_user = User(
                username=f"kakao_{social_id}",  # 유니크한 username 생성
                email=email,
                full_name=nickname,
                provider="kakao",
                social_id=social_id,
                is_active=True
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user

    # 4. JWT 토큰 발급
    access_token = create_access_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }



# ==========================================
# 네이버 소셜 로그인
# ==========================================
import secrets
from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REDIRECT_URI

NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"


@router.get("/naver/login", tags=["Authentication"])
def naver_login():
    """
    네이버 로그인 페이지로 리디렉션
    """
    state = secrets.token_urlsafe(16)
    redirect_url = (
        f"{NAVER_AUTH_URL}?response_type=code&client_id={NAVER_CLIENT_ID}"
        f"&redirect_uri={NAVER_REDIRECT_URI}&state={state}"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/naver/callback", response_model=TokenResponse, tags=["Authentication"])
async def naver_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    네이버 로그인 콜백 처리
    """
    # 1. 인증 코드로 액세스 토큰 받기
    token_data = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": code,
        "state": state,
    }
    async with httpx.AsyncClient() as client:
        token_response = await client.post(NAVER_TOKEN_URL, data=token_data)
        token_response.raise_for_status()
        naver_token = token_response.json()

    # 2. 액세스 토큰으로 사용자 정보 받기
    headers = {"Authorization": f"Bearer {naver_token['access_token']}"}
    async with httpx.AsyncClient() as client:
        user_info_response = await client.get(NAVER_USER_INFO_URL, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()["response"]

    social_id = user_info["id"]
    email = user_info["email"]
    nickname = user_info["name"]
    # profile_image = user_info["profile_image"] # 프로필 사진, 필요 시 사용

    # 3. 사용자 정보로 DB 조회 및 생성
    user = db.query(User).filter(User.social_id == social_id, User.provider == "naver").first()

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.provider = "naver"
            user.social_id = social_id
            db.commit()
        else:
            new_user = User(
                username=f"naver_{social_id}",
                email=email,
                full_name=nickname,
                provider="naver",
                social_id=social_id,
                is_active=True
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user

    # 4. JWT 토큰 발급
    access_token = create_access_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

