"""
User database model

SQLAlchemy ORM을 사용하여 사용자 정보를 데이터베이스에 저장합니다.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime

from app.core.database import Base


class User(Base):
    """
    사용자 테이블 (ORM Model)

    회원가입한 사용자의 정보를 저장하는 데이터베이스 테이블입니다.
    SQLAlchemy ORM을 통해 Python 객체로 다룰 수 있습니다.

    Attributes:
        id (int): 사용자 고유 ID (Primary Key, 자동 증가)
        email (str): 이메일 주소 (unique, 로그인 시 사용)
        hashed_password (str): bcrypt로 해시된 비밀번호 (평문 저장 금지!)
        full_name (str, optional): 사용자 이름
        phone (str, optional): 전화번호
        is_active (bool): 계정 활성화 여부 (회원탈퇴 시 False)
        created_at (datetime): 계정 생성 일시 (자동 설정)
        updated_at (datetime): 계정 수정 일시 (자동 업데이트)

    Example:
        >>> from app.core.database import SessionLocal
        >>> from app.core.security import get_password_hash
        >>>
        >>> db = SessionLocal()
        >>> new_user = User(
        ...     email="john@example.com",
        ...     hashed_password=get_password_hash("mypassword123")
        ... )
        >>> db.add(new_user)
        >>> db.commit()
    """
    __tablename__ = "users"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, comment="사용자 고유 ID")

    # 로그인 정보 (unique 제약조건)
    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
        comment="이메일 주소 (로그인 시 사용)"
    )
    hashed_password = Column(
        String,
        nullable=True,  # 소셜 로그인을 위해 Null 허용
        comment="bcrypt로 해시된 비밀번호"
    )

    # 소셜 로그인 정보
    provider = Column(String, nullable=True, comment="소셜 로그인 제공자 (e.g., kakao)")
    social_id = Column(String, nullable=True, unique=True, index=True, comment="소셜 ID")

    # 사용자 정보 (optional)
    full_name = Column(String, nullable=True, comment="사용자 이름")
    phone = Column(String, nullable=True, comment="전화번호")

    # 계정 상태
    is_active = Column(
        Boolean,
        default=True,
        comment="계정 활성화 여부 (회원탈퇴 시 False)"
    )

    # 타임스탬프 (자동 설정)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="계정 생성 일시"
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="계정 수정 일시"
    )

    def __repr__(self):
        """객체를 문자열로 표현 (디버깅용)"""
        return f"<User(id={self.id}, email='{self.email}')>"
