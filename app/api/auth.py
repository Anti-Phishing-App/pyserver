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

    새로운 사용자 계정을 생성합니다.

    Args:
        request: 회원가입 요청 데이터 (email, password 등)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        UserResponse: 생성된 사용자 정보 (비밀번호 제외)

    Raises:
        HTTPException 400: 이미 사용 중인 email

    Example:
        ```bash
        curl -X POST "http://localhost:8000/auth/signup" \\
             -H "Content-Type: application/json" \\
             -d '{
               "email": "john@example.com",
               "password": "securepass123!",
               "full_name": "John Doe"
             }'
        ```
    """
    # 중복 체크 - email
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 새 사용자 생성
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

    # 토큰 생성
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
    # 리프레시 토큰 검증
    payload = decode_token(request.refresh_token, JWT_SECRET_KEY, JWT_ALGORITHM)

    # 토큰 타입 확인
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

    # 사용자 존재 확인
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # 새 토큰 발급
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

    소셜 로그인으로 가입한 사용자가 전화번호, 이름 등 추가 정보를 입력합니다.

    Args:
        request: 추가 정보 (phone, full_name)
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserResponse: 업데이트된 사용자 정보

    Example:
        ```bash
        curl -X POST "http://localhost:8000/auth/additional-info" \\
             -H "Authorization: Bearer {access_token}" \\
             -H "Content-Type: application/json" \\
             -d '{
               "phone": "010-1234-5678",
               "full_name": "홍길동"
             }'
        ```
    """
    # 추가 정보 업데이트
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

# 주의: 이 임시 저장소는 프로덕션 환경에 적합하지 않습니다.
# 동시성 문제 및 확장성 문제가 발생할 수 있습니다.
# 프로덕션에서는 Redis, 데이터베이스 또는 JWT 기반의 state를 사용해야 합니다.
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

    Args:
        final_redirect_uri: 로그인 성공 후 최종적으로 리디렉션할 클라이언트 측 URL.
                            (예: 웹사이트의 특정 페이지, 앱의 딥링크)
                            지정하지 않으면 웹 기본 성공 URL로 이동합니다.
    """
    state = secrets.token_urlsafe(16)
    # 최종 리디렉션 URI를 state와 함께 임시 저장
    _temp_state_storage[state] = final_redirect_uri or WEB_SUCCESS_REDIRECT_URL

    redirect_url = (
        f"{KAKAO_AUTH_URL}?client_id={KAKAO_CLIENT_ID}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}&response_type=code"
        f"&scope=account_email&state={state}"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/kakao/callback", tags=["Authentication"])
async def kakao_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    카카오 로그인 콜백 처리

    카카오로부터 받은 인증 코드로 토큰을 받고, 사용자 정보를 조회하여
    JWT 토큰을 발급한 뒤, 최종적으로 지정된 URL로 리디렉션합니다.
    """
    # 1. state 값으로 최종 리디렉션 URI 가져오기
    final_redirect_uri = _temp_state_storage.pop(state, WEB_SUCCESS_REDIRECT_URL)

    # 2. 인증 코드로 액세스 토큰 받기
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

    # 3. 사용자 정보 받기
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

    # 4. 사용자 정보로 DB 조회 및 생성
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
            db.commit()
        else:
            new_user = User(email=email, full_name=nickname, provider="kakao", social_id=social_id, is_active=True)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
            requires_info = True

    if not user.phone:
        requires_info = True

    # 5. JWT 토큰 발급
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

    # 6. 최종 URI로 리디렉션
    redirect_params = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_additional_info": str(requires_info).lower()
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
    """
    state = secrets.token_urlsafe(16)
    # 최종 리디렉션 URI를 state와 함께 임시 저장
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
    # 1. state 값으로 최종 리디렉션 URI 가져오기
    final_redirect_uri = _temp_state_storage.pop(state, WEB_SUCCESS_REDIRECT_URL)

    # 2. 인증 코드로 액세스 토큰 받기
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

    # 3. 액세스 토큰으로 사용자 정보 받기
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
    nickname = user_info.get("name")

    # 4. 사용자 정보로 DB 조회 및 생성
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
            db.commit()
        else:
            new_user = User(email=email, full_name=nickname, provider="naver", social_id=social_id, is_active=True)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
            requires_info = True

    if not user.phone:
        requires_info = True

    # 5. JWT 토큰 발급
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

    # 6. 최종 URI로 리디렉션
    redirect_params = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_additional_info": str(requires_info).lower() # bool to string
    }
    redirect_url = generate_final_redirect_url(final_redirect_uri, redirect_params)

    return RedirectResponse(url=redirect_url)

