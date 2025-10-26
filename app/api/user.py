"""
User management API endpoints

사용자 관리 관련 API 엔드포인트를 정의합니다.
- 내 정보 조회/수정
- 회원탈퇴 (soft delete)
- 아이디 찾기 (이메일 기반)
- 비밀번호 재설정

Note:
    이 API들은 대부분 인증이 필요합니다. (Authorization 헤더 필요)
    아이디 찾기와 비밀번호 재설정은 인증 불필요합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserUpdateRequest,
    FindUsernameRequest,
    FindUsernameResponse,
    ResetPasswordRequest,
    MessageResponse
)

router = APIRouter(prefix="/user")


@router.get("/me", response_model=UserResponse)
def get_my_info(current_user: User = Depends(get_current_user)):
    """
    내 정보 조회

    현재 로그인한 사용자의 정보를 조회합니다.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_my_info(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    내 정보 수정

    현재 로그인한 사용자의 정보를 수정합니다.
    비밀번호 변경 시 현재 비밀번호 확인이 필요합니다.
    """
    # 비밀번호 변경 요청 시
    if request.new_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to change password"
            )

        # 현재 비밀번호 확인
        if not verify_password(request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect current password"
            )

        # 새 비밀번호로 변경
        current_user.hashed_password = get_password_hash(request.new_password)

    # 이메일 변경 시 중복 체크
    if request.email and request.email != current_user.email:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = request.email

    # 기타 정보 업데이트
    if request.full_name is not None:
        current_user.full_name = request.full_name

    if request.phone is not None:
        current_user.phone = request.phone

    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/me", response_model=MessageResponse)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    회원탈퇴

    현재 로그인한 사용자의 계정을 비활성화합니다.
    실제로는 is_active를 False로 변경합니다 (soft delete).
    데이터는 남아있지만 로그인할 수 없습니다.

    Args:
        current_user: 현재 인증된 사용자 (자동 주입)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        MessageResponse: 성공 메시지

    Example:
        ```bash
        curl -X DELETE "http://localhost:8000/user/me" \\
             -H "Authorization: Bearer {access_token}"
        ```
    """
    # Soft delete: is_active를 False로 설정
    current_user.is_active = False
    db.commit()

    return {"message": "Account successfully deactivated"}


@router.post("/find-username", response_model=FindUsernameResponse)
def find_username(request: FindUsernameRequest, db: Session = Depends(get_db)):
    """
    아이디 찾기

    이메일을 통해 사용자 아이디를 찾습니다.
    회원가입 시 등록한 이메일로 아이디를 조회합니다.

    Args:
        request: 아이디 찾기 요청 (email)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        FindUsernameResponse: 찾은 아이디와 가입일

    Raises:
        HTTPException 404: 해당 이메일로 가입된 계정 없음

    Example:
        ```bash
        curl -X POST "http://localhost:8000/user/find-username" \\
             -H "Content-Type: application/json" \\
             -d '{"email": "john@example.com"}'
        ```

        Response:
        ```json
        {
          "username": "john_doe",
          "created_at": "2025-10-26T10:00:00"
        }
        ```
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with this email"
        )

    return {
        "username": user.username,
        "created_at": user.created_at
    }


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    비밀번호 재설정

    이메일과 아이디를 확인하여 비밀번호를 재설정합니다.

    Warning:
        실제 서비스에서는 이메일 인증 코드 발송 등의 추가 보안 절차가 필요합니다.
        현재는 단순히 이메일+아이디 조합만 확인합니다.

    Args:
        request: 비밀번호 재설정 요청 (email, username, new_password)
        db: 데이터베이스 세션 (자동 주입)

    Returns:
        MessageResponse: 성공 메시지

    Raises:
        HTTPException 404: 해당 이메일+아이디 조합의 계정 없음

    Example:
        ```bash
        curl -X POST "http://localhost:8000/user/reset-password" \\
             -H "Content-Type: application/json" \\
             -d '{
               "email": "john@example.com",
               "username": "john_doe",
               "new_password": "newpassword123!"
             }'
        ```

        Response:
        ```json
        {
          "message": "Password successfully reset"
        }
        ```
    """
    # 사용자 찾기
    user = db.query(User).filter(
        User.email == request.email,
        User.username == request.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with this email and username combination"
        )

    # 비밀번호 재설정
    user.hashed_password = get_password_hash(request.new_password)
    db.commit()

    return {"message": "Password successfully reset"}
