"""
Authentication schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class SignupRequest(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., min_length=8, max_length=100, description="비밀번호 (최소 8자)")
    full_name: Optional[str] = Field(None, max_length=100, description="이름")
    phone: Optional[str] = Field(None, max_length=20, description="전화번호")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "securepass123!",
                "full_name": "John Doe",
                "phone": "010-1234-5678"
            }
        }


class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., description="비밀번호")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "securepass123!"
            }
        }


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    requires_additional_info: bool = Field(default=False, description="추가 정보 입력 필요 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "requires_additional_info": False
            }
        }


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청"""
    refresh_token: str = Field(..., description="리프레시 토큰")

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class AdditionalInfoRequest(BaseModel):
    """소셜 로그인 후 추가 정보 입력 요청"""
    phone: Optional[str] = Field(None, max_length=20, description="전화번호")
    full_name: Optional[str] = Field(None, max_length=100, description="이름")

    class Config:
        json_schema_extra = {
            "example": {
                "phone": "010-1234-5678",
                "full_name": "홍길동"
            }
        }
