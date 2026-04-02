from __future__ import annotations
import asyncio, contextlib, json, os
from typing import AsyncIterator, Optional

# 🔥 여기 핵심 수정
from app.config import (
    CLOVA_GRPC_SECRET_KEY,
    CLOVA_GRPC_HOST,
    CLOVA_GRPC_PORT,
)

from grpc_client.clova_grpc_client import ClovaSpeechClient


class BaseSTTStream:
    async def feed(self, chunk: bytes): raise NotImplementedError
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): await self.close()
    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        raise NotImplementedError


# =========================
# WebSocket STT (옵션)
# =========================
import websockets

class WebsocketSTTStream(BaseSTTStream):
    def __init__(self, stt_ws_url: str, sample_rate: int = 16000):
        sep = "&" if "?" in stt_ws_url else "?"
        self.stt_ws_url = f"{stt_ws_url}{sep}sr={sample_rate}"
        self._conn: Optional[websockets.WebSocketClientProtocol] = None
        self._audio_q: asyncio.Queue[bytes] = asyncio.Queue()
        self._closed = asyncio.Event()

    async def __aenter__(self):
        self._conn = await websockets.connect(self.stt_ws_url)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def feed(self, chunk: bytes):
        await self._audio_q.put(chunk)

    async def close(self):
        self._closed.set()
        with contextlib.suppress(Exception):
            if self._conn:
                await self._conn.close()

    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        assert self._conn is not None
        sender = asyncio.create_task(self._send_audio())

        try:
            async for msg in self._conn:
                data = json.loads(msg)
                text = data.get("text") or ""
                is_final = (data.get("type") == "final")

                if text:
                    yield text, is_final

                if self._closed.is_set():
                    break
        finally:
            sender.cancel()
            with contextlib.suppress(Exception):
                await sender

    async def _send_audio(self):
        assert self._conn is not None
        while not self._closed.is_set():
            try:
                chunk = await asyncio.wait_for(self._audio_q.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            await self._conn.send(chunk)


# =========================
# 🔥 CLOVA gRPC STT (핵심)
# =========================
class GrpcSTTStream(BaseSTTStream):
    def __init__(self, sample_rate: int = 16000, language: str = "ko-KR"):

        # 🔥 완전히 분리된 키 사용
        if not CLOVA_GRPC_SECRET_KEY:
            raise RuntimeError("CLOVA_GRPC_SECRET_KEY 환경변수가 필요합니다.")

        self.sample_rate = sample_rate
        self.language = language or "ko-KR"

        self._audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = asyncio.Event()

        # 🔥 핵심 (gRPC 전용 key)
        self._client = ClovaSpeechClient(
            secret_key=CLOVA_GRPC_SECRET_KEY,
            host=CLOVA_GRPC_HOST,
            port=CLOVA_GRPC_PORT,
        )

        config_payload = {
            "transcription": {
                "language": self._short_lang(self.language)
            },
            "semanticEpd": _semantic_epd_config(),
        }

        kb = _keyword_boosting_from_env()
        if kb:
            config_payload["keywordBoosting"] = kb

        forbidden = _forbidden_from_env()
        if forbidden:
            config_payload["forbidden"] = forbidden

        self._config_json = json.dumps(config_payload, ensure_ascii=False)

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def feed(self, chunk: bytes):
        if not self._closed.is_set():
            await self._audio_q.put(chunk)

    async def close(self):
        if not self._closed.is_set():
            self._closed.set()
            await self._audio_q.put(None)

        with contextlib.suppress(Exception):
            await self._client.close()

    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        try:
            async for response in self._client.recognize(
                self._audio_q,
                config_json=self._config_json,
                language=self.language,
            ):
                contents = getattr(response, "contents", "")
                if not contents:
                    continue

                try:
                    payload = json.loads(contents)
                except json.JSONDecodeError:
                    continue

                tr = payload.get("transcription")
                if not isinstance(tr, dict):
                    continue

                text = (tr.get("text") or "").strip()
                if not text:
                    continue

                yield text, bool(tr.get("isFinal", False))

                if self._closed.is_set():
                    break
        finally:
            await self.close()

    @staticmethod
    def _short_lang(lang: str) -> str:
        lang = (lang or "ko-KR").lower()
        if lang.startswith("ko"):
            return "ko"
        if lang.startswith("en"):
            return "en"
        if lang.startswith("ja"):
            return "ja"
        return lang.split("-")[0]


# =========================
# 옵션 설정
# =========================
def _semantic_epd_config() -> dict:
    def _bool_env(name: str, default: bool) -> bool:
        val = os.getenv(name)
        if val is None:
            return default
        return val.lower() in {"1", "true", "yes", "on"}

    cfg = {
        "skipEmptyText": _bool_env("STT_SEMANTIC_SKIP_EMPTY", True),
        "useWordEpd": _bool_env("STT_SEMANTIC_USE_WORD", True),
        "usePeriodEpd": _bool_env("STT_SEMANTIC_USE_PERIOD", True),
    }

    return cfg


def _keyword_boosting_from_env() -> Optional[dict]:
    raw = os.getenv("STT_KEYWORD_BOOSTINGS")
    if not raw:
        return None

    boostings = []
    for entry in raw.split(";"):
        if ":" in entry:
            words, weight = entry.split(":", 1)
            try:
                weight = float(weight)
            except:
                continue
        else:
            words = entry
            weight = 1.0

        boostings.append({
            "words": words.strip(),
            "weight": weight
        })

    return {"boostings": boostings} if boostings else None


def _forbidden_from_env() -> Optional[dict]:
    raw = os.getenv("STT_FORBIDDEN_WORDS")
    if not raw:
        return None

    words = ",".join(w.strip() for w in raw.split(",") if w.strip())
    return {"forbiddens": words} if words else None
