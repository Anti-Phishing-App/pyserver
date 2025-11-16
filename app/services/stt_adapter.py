# app/services/stt_adapter.py
from __future__ import annotations
import asyncio, contextlib, json, os
from typing import AsyncIterator, Optional

from app.config import CLOVA_SECRET_KEY
from grpc_client.clova_grpc_client import ClovaSpeechClient


class BaseSTTStream:
    async def feed(self, chunk: bytes): raise NotImplementedError
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): await self.close()
    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        """yield (text, is_final)"""
        raise NotImplementedError

# --- WebSocket 기반 STT 공급자 예시(옵션) ---
# 환경변수 STT_WS_URL=wss://stt.example.com/stream
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

    async def feed(self, chunk: bytes): await self._audio_q.put(chunk)

    async def close(self):
        self._closed.set()
        with contextlib.suppress(Exception):
            if self._conn: await self._conn.close()

    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        assert self._conn is not None, "STT WebSocket not connected"
        sender = asyncio.create_task(self._send_audio())
        try:
            async for msg in self._conn:
                data = json.loads(msg)  # 공급자 포맷에 맞게 조정
                text = data.get("text") or ""
                is_final = (data.get("type") == "final")
                if text:
                    yield text, is_final
                if self._closed.is_set():
                    break
        finally:
            sender.cancel()
            with contextlib.suppress(Exception): await sender

    async def _send_audio(self):
        assert self._conn is not None
        while not self._closed.is_set():
            try:
                chunk = await asyncio.wait_for(self._audio_q.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            await self._conn.send(chunk)

# --- CLOVA gRPC 기반 STT 구현 ---
class GrpcSTTStream(BaseSTTStream):
    def __init__(self, sample_rate: int = 16000, language: str = "ko-KR"):
        if not CLOVA_SECRET_KEY:
            raise RuntimeError("CLOVA_SECRET_KEY 환경변수가 필요합니다.")
        self.sample_rate = sample_rate
        self.language = language or "ko-KR"
        self._audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = asyncio.Event()
        self._client = ClovaSpeechClient(secret_key=CLOVA_SECRET_KEY)
        config_payload = {
            "transcription": {"language": self._short_lang(self.language)},
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
        if self._closed.is_set():
            return
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
    gap = os.getenv("STT_SEMANTIC_GAP_MS", "600")
    duration = os.getenv("STT_SEMANTIC_DURATION_MS", "1000")
    syllable = os.getenv("STT_SEMANTIC_SYLLABLES", "5")
    for key, raw in (
        ("gapThreshold", gap),
        ("durationThreshold", duration),
        ("syllableThreshold", syllable),
    ):
        try:
            val = int(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            cfg[key] = val
    return cfg


def _keyword_boosting_from_env() -> Optional[dict]:
    """
    STT_KEYWORD_BOOSTINGS="단어1,단어2:1.5;기타:1.0"
    """
    raw = os.getenv("STT_KEYWORD_BOOSTINGS")
    if not raw:
        return None
    boostings = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            words_part, weight_part = entry.split(":", 1)
        else:
            words_part, weight_part = entry, "1.0"
        try:
            weight = float(weight_part)
        except ValueError:
            continue
        boostings.append({"words": words_part.strip(), "weight": weight})
    return {"boostings": boostings} if boostings else None


def _forbidden_from_env() -> Optional[dict]:
    raw = os.getenv("STT_FORBIDDEN_WORDS")
    if not raw:
        return None
    words = ",".join(filter(None, (w.strip() for w in raw.split(","))))
    return {"forbiddens": words} if words else None
