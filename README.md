# pyserver
Python FastAPI 기반 피싱 탐지 서버

## 개요
보이스피싱, 문서 위조, URL 피싱, SMS 피싱 등을 탐지하는 AI 기반 서버

## 주요 기능
- 🔐 JWT 기반 사용자 인증 (회원가입/로그인/로그아웃)
- 👤 사용자 관리 (회원탈퇴, 아이디/비밀번호 찾기)
- 📞 보이스피싱 탐지 (STT + AI 분석)
- 📄 문서 위조 탐지 (OCR + 이미지 분석)
- 🌐 URL 피싱 탐지 (예정)
- 💬 SMS 피싱 탐지 (예정)

## 디렉토리 구조

```
 pyserver/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py                      # FastAPI 앱 초기화, 라우터 등록
  │   ├── config.py                    # 환경변수 관리 (JWT, DB, API 키)
  │   │
  │   ├── core/                        # 핵심 기능 ✅
  │   │   ├── __init__.py
  │   │   ├── database.py              # SQLAlchemy DB 연결 및 세션 관리
  │   │   ├── security.py              # JWT 토큰 생성/검증, 비밀번호 해싱
  │   │   └── dependencies.py          # FastAPI 의존성 함수 (인증)
  │   │
  │   ├── models/                      # ORM 모델 (DB 테이블) ✅
  │   │   ├── __init__.py
  │   │   └── user.py                  # User 테이블 (username, email, password 등)
  │   │
  │   ├── schemas/                     # Pydantic 스키마 (요청/응답) ✅
  │   │   ├── __init__.py
  │   │   ├── auth.py                  # 로그인/회원가입 요청/응답
  │   │   └── user.py                  # 사용자 정보 요청/응답
  │   │
  │   ├── api/                         # API 라우터 ✅
  │   │   ├── __init__.py
  │   │   ├── auth.py                  # 인증 API (회원가입, 로그인, 토큰 갱신)
  │   │   ├── user.py                  # 사용자 관리 API (탈퇴, 정보수정, 찾기)
  │   │   ├── transcribe.py            # 음성 변환 API (STT)
  │   │   ├── document.py              # 문서 위조 탐지 API
  │   │   └── upload.py                # 파일 업로드 API
  │   │
  │   ├── services/                    # 비즈니스 로직
  │   │   └── __init__.py
  │   │
  │   ├── ml/                          # AI 모델
  │   │   └── __init__.py
  │   │
  │   └── utils/                       # 공통 유틸리티
  │       ├── __init__.py
  │       └── ...
  │
  ├── grpc_client/                     # gRPC 클라이언트 (CLOVA STT)
  │   └── ...
  │
  ├── legacy/                          # 기존 코드 (마이그레이션 전)
  │   └── ...
  │
  ├── uploads/                         # 업로드 파일 저장소
  ├── .env                             # 환경변수 파일 (git ignore)
  ├── .gitignore
  ├── requirements.txt                 # Python 의존성
  ├── README.md
  └── index.html                       # 프론트엔드 페이지
```

## 데이터베이스

### User 테이블
```python
- id: 기본키
- username: 사용자 아이디 (unique)
- email: 이메일 (unique)
- hashed_password: 해시된 비밀번호
- full_name: 이름
- phone: 전화번호
- is_active: 활성화 여부
- created_at: 생성일시
- updated_at: 수정일시
```

## 보안

- 비밀번호: bcrypt 해싱
- 인증: JWT (HS256)
- 액세스 토큰: 30분 유효
- 리프레시 토큰: 7일 유효