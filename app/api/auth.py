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

    Args:
        request: 로그인 요청 데이터 (username, password)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        TokenResponse: JWT 액세스 토큰 + 리프레시 토큰

    Raises:
        HTTPException 401: 잘못된 username 또는 password

    Example:
        ```bash
        curl -X POST "http://localhost:8000/auth/login" \\
             -H "Content-Type: application/json" \\
             -d '{
               "username": "john_doe",
               "password": "securepass123!"
             }'
        ```

        Response:
        ```json
        {
          "access_token": "eyJhbGc...",
          "refresh_token": "eyJhbGc...",
          "token_type": "bearer"
        }
        ```

        이후 API 요청 시 헤더에 포함:
        ```
        Authorization: Bearer {access_token}
        ```
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
