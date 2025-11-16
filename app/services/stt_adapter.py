# app/services/stt_adapter.py
from __future__ import annotations
import asyncio, contextlib, json, os
from typing import AsyncIterator, Optional

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
        self.stt_ws_url = f"{stt_ws_url}?sr={sample_rate}"
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

# --- CLOVA 등 gRPC 기반 STT 골격(기존 구현 옮겨 넣기) ---
class GrpcSTTStream(BaseSTTStream):
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._audio_q: asyncio.Queue[bytes] = asyncio.Queue()
        self._closed = asyncio.Event()
        # TODO: 기존 CLOVA gRPC 채널/스텁 초기화

    async def feed(self, chunk: bytes): await self._audio_q.put(chunk)
    async def close(self): self._closed.set()

    async def transcripts(self) -> AsyncIterator[tuple[str, bool]]:
        # TODO: 기존 레포의 양방향 스트리밍 코드를 이곳으로 옮겨
        #  (큐에서 오디오 꺼내 write, 응답에서 partial/final 읽어 yield)
        while not self._closed.is_set():
            await asyncio.sleep(0.05)
