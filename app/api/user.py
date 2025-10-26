"""
User management API endpoints
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

    현재 로그인한 사용자의 계정을 삭제합니다.
    실제로는 is_active를 False로 변경합니다 (soft delete).
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
    실제 서비스에서는 이메일 인증 등의 추가 보안 절차가 필요합니다.
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
