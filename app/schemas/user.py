"""
User schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """사용자 정보 응답"""
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "phone": "010-1234-5678",
                "is_active": True,
                "created_at": "2025-10-26T10:00:00",
                "updated_at": "2025-10-26T10:00:00"
            }
        }


class UserUpdateRequest(BaseModel):
    """사용자 정보 수정 요청"""
    email: Optional[EmailStr] = Field(None, description="이메일")
    full_name: Optional[str] = Field(None, max_length=100, description="이름")
    phone: Optional[str] = Field(None, max_length=20, description="전화번호")
    current_password: Optional[str] = Field(None, description="현재 비밀번호 (비밀번호 변경 시 필수)")
    new_password: Optional[str] = Field(None, min_length=8, max_length=100, description="새 비밀번호")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "full_name": "John Updated",
                "phone": "010-9876-5432"
            }
        }


class FindUsernameRequest(BaseModel):
    """아이디 찾기 요청"""
    email: EmailStr = Field(..., description="가입 시 사용한 이메일")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com"
            }
        }


class FindUsernameResponse(BaseModel):
    """아이디 찾기 응답"""
    username: str = Field(..., description="찾은 사용자 아이디")
    created_at: datetime = Field(..., description="가입 날짜")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "created_at": "2025-10-26T10:00:00"
            }
        }


class ResetPasswordRequest(BaseModel):
    """비밀번호 재설정 요청"""
    email: EmailStr = Field(..., description="가입 시 사용한 이메일")
    username: str = Field(..., description="사용자 아이디")
    new_password: str = Field(..., min_length=8, max_length=100, description="새 비밀번호 (최소 8자)")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "username": "john_doe",
                "new_password": "newsecurepass123!"
            }
        }


class MessageResponse(BaseModel):
    """일반 메시지 응답"""
    message: str = Field(..., description="응답 메시지")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "작업이 성공적으로 완료되었습니다."
            }
        }
