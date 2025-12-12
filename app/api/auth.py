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
    RefreshTokenRequest,
    AdditionalInfoRequest
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
    """
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    new_user = User(
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
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    refresh_token = create_refresh_token(
        data={"sub": user.email},
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
    payload = decode_token(request.refresh_token, JWT_SECRET_KEY, JWT_ALGORITHM)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    new_access_token = create_access_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    new_refresh_token = create_refresh_token(
        data={"sub": user.email},
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


@router.post("/additional-info", response_model=UserResponse)
def update_additional_info(
    request: AdditionalInfoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    소셜 로그인 후 추가 정보 입력
    """
    if request.phone is not None:
        current_user.phone = request.phone

    if request.full_name is not None:
        current_user.full_name = request.full_name

    db.commit()
    db.refresh(current_user)

    return current_user


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보 조회
    """
    return current_user


# ==========================================
# 소셜 로그인 (공통)
# ==========================================
import secrets
import urllib.parse

_temp_state_storage = {}


def generate_final_redirect_url(base_url: str, params: dict) -> str:
    """최종 리디렉션 URL을 생성합니다."""
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


# ==========================================
# 카카오 소셜 로그인
# ==========================================
import httpx
from fastapi.responses import RedirectResponse
from app.config import (
    KAKAO_CLIENT_ID,
    KAKAO_REDIRECT_URI,
    WEB_SUCCESS_REDIRECT_URL
)

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/kakao/login", tags=["Authentication"])
def kakao_login(final_redirect_uri: str = None):
    """
    카카오 로그인 페이지로 리디렉션

    - 앱 재실행 자동로그인(=refresh) 흐름 방해하지 않도록 prompt 강제옵션 없음
    - 닉네임 받기 위해 profile_nickname scope 추가
    """
    state = secrets.token_urlsafe(16)
    _temp_state_storage[state] = final_redirect_uri or WEB_SUCCESS_REDIRECT_URL

    redirect_url = (
        f"{KAKAO_AUTH_URL}?client_id={KAKAO_CLIENT_ID}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}&response_type=code"
        f"&scope=account_email,profile_nickname&state={state}"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/kakao/callback", tags=["Authentication"])
async def kakao_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    카카오 로그인 콜백 처리
    """
    final_redirect_uri = _temp_state_storage.pop(state, WEB_SUCCESS_REDIRECT_URL)

    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    async with httpx.AsyncClient() as client:
        token_response = await client.post(KAKAO_TOKEN_URL, data=token_data)
        if token_response.status_code != 200:
            error_detail = token_response.json().get("error_description", "Failed to get token from Kakao.")
            redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
            return RedirectResponse(url=redirect_url)
        kakao_token = token_response.json()

    headers = {"Authorization": f"Bearer {kakao_token['access_token']}"}
    async with httpx.AsyncClient() as client:
        user_info_response = await client.get(KAKAO_USER_INFO_URL, headers=headers)
        if user_info_response.status_code != 200:
            error_detail = "Failed to get user info from Kakao."
            redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
            return RedirectResponse(url=redirect_url)
        user_info = user_info_response.json()

    social_id = str(user_info.get("id"))
    email = user_info.get("kakao_account", {}).get("email")
    if not email:
        redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": "Email permission is required."})
        return RedirectResponse(url=redirect_url)

    nickname = (
        user_info.get("properties", {}).get("nickname")
        or user_info.get("kakao_account", {}).get("profile", {}).get("nickname")
        or "카카오사용자"
    )

    user = db.query(User).filter(User.social_id == social_id, User.provider == "kakao").first()

    requires_info = False
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.provider and user.provider != "kakao":
                error_detail = f"This email is already linked to {user.provider} login"
                redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
                return RedirectResponse(url=redirect_url)

            user.provider = "kakao"
            user.social_id = social_id

            # 기존 계정에 카카오 연결되는 경우에도 placeholder면 nickname 업데이트
            if (not user.full_name) or (user.full_name == "카카오사용자"):
                if nickname and nickname != "카카오사용자":
                    user.full_name = nickname

            db.commit()
            db.refresh(user)
        else:
            new_user = User(
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
            requires_info = True
    else:
        # 이미 카카오 유저여도 placeholder면 nickname으로 갱신
        if (not user.full_name) or (user.full_name == "카카오사용자"):
            if nickname and nickname != "카카오사용자":
                user.full_name = nickname
                db.commit()
                db.refresh(user)

    if not user.phone:
        requires_info = True

    access_token = create_access_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    redirect_params = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_additional_info": str(requires_info).lower(),
        # 앱에서 바로 닉네임 표시 가능하도록 추가
        "nickname": user.full_name or nickname,
        "provider": "kakao",
        "email": user.email
    }
    redirect_url = generate_final_redirect_url(final_redirect_uri, redirect_params)

    return RedirectResponse(url=redirect_url)


# ==========================================
# 네이버 소셜 로그인
# ==========================================
from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REDIRECT_URI

NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"


@router.get("/naver/login", tags=["Authentication"])
def naver_login(final_redirect_uri: str = None):
    """
    네이버 로그인 페이지로 리디렉션

    - 앱 재실행 자동로그인(=refresh) 흐름 방해하지 않도록 강제 재인증 옵션 없음
    """
    state = secrets.token_urlsafe(16)
    _temp_state_storage[state] = final_redirect_uri or WEB_SUCCESS_REDIRECT_URL

    redirect_url = (
        f"{NAVER_AUTH_URL}?response_type=code&client_id={NAVER_CLIENT_ID}"
        f"&redirect_uri={NAVER_REDIRECT_URI}&state={state}"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/naver/callback", tags=["Authentication"])
async def naver_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    네이버 로그인 콜백 처리
    """
    final_redirect_uri = _temp_state_storage.pop(state, WEB_SUCCESS_REDIRECT_URL)

    token_data = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": code,
        "state": state,
    }
    async with httpx.AsyncClient() as client:
        token_response = await client.post(NAVER_TOKEN_URL, data=token_data)
        if token_response.status_code != 200:
            error_detail = token_response.json().get("error_description", "Failed to get token from Naver.")
            redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
            return RedirectResponse(url=redirect_url)
        naver_token = token_response.json()

    headers = {"Authorization": f"Bearer {naver_token['access_token']}"}
    async with httpx.AsyncClient() as client:
        user_info_response = await client.get(NAVER_USER_INFO_URL, headers=headers)
        if user_info_response.status_code != 200:
            error_detail = "Failed to get user info from Naver."
            redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
            return RedirectResponse(url=redirect_url)
        user_info = user_info_response.json().get("response")
        if not user_info:
            error_detail = "Failed to parse user info from Naver."
            redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
            return RedirectResponse(url=redirect_url)

    social_id = user_info.get("id")
    email = user_info.get("email")
    nickname = user_info.get("name") or "네이버사용자"

    user = db.query(User).filter(User.social_id == social_id, User.provider == "naver").first()

    requires_info = False

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.provider and user.provider != "naver":
                error_detail = f"This email is already linked to {user.provider} login"
                redirect_url = generate_final_redirect_url(final_redirect_uri, {"error": error_detail})
                return RedirectResponse(url=redirect_url)

            user.provider = "naver"
            user.social_id = social_id

            # 기존 계정에 네이버 연결되는 경우에도 placeholder면 nickname 업데이트
            if (not user.full_name) or (user.full_name == "네이버사용자"):
                if nickname and nickname != "네이버사용자":
                    user.full_name = nickname

            db.commit()
            db.refresh(user)
        else:
            new_user = User(
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
            requires_info = True
    else:
        # 이미 네이버 유저여도 placeholder면 nickname으로 갱신
        if (not user.full_name) or (user.full_name == "네이버사용자"):
            if nickname and nickname != "네이버사용자":
                user.full_name = nickname
                db.commit()
                db.refresh(user)

    if not user.phone:
        requires_info = True

    access_token = create_access_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email},
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        expires_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    redirect_params = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_additional_info": str(requires_info).lower(),
        # 앱에서 바로 닉네임 표시 가능하도록 추가
        "nickname": user.full_name or nickname,
        "provider": "naver",
        "email": user.email
    }
    redirect_url = generate_final_redirect_url(final_redirect_uri, redirect_params)

    return RedirectResponse(url=redirect_url)
