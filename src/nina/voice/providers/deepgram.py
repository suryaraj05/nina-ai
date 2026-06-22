"""Deepgram streaming STT over WebSocket. Standalone — imports nothing from
NINA core. Requires the optional dependency: pip install nina-sdk[deepgram]
"""
import asyncio
import json
import logging
from urllib.parse import urlencode

import websockets

from ..adapter import InputAdapter

logger = logging.getLogger("nina.voice.deepgram")

_CHUNK = 3200  # 100 ms of linear16 @ 16 kHz


class DeepgramProvider(InputAdapter):
    def __init__(self, api_key, model="nova-2", language="en",
                 encoding="linear16", sample_rate=16000):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.encoding = encoding
        self.sample_rate = sample_rate

    @property
    def supports_streaming(self) -> bool:
        return True

    def _url(self) -> str:
        query = urlencode({"model": self.model, "language": self.language,
                           "encoding": self.encoding,
                           "sample_rate": self.sample_rate,
                           "punctuate": "true"})
        return f"wss://api.deepgram.com/v1/listen?{query}"

    async def _pump(self, ws, audio_stream):
        try:
            if isinstance(audio_stream, (bytes, bytearray)):
                await ws.send(bytes(audio_stream))
            elif isinstance(audio_stream, asyncio.StreamReader):
                while chunk := await audio_stream.read(_CHUNK):
                    await ws.send(chunk)
            else:  # async iterator of bytes chunks
                async for chunk in audio_stream:
                    await ws.send(chunk)
        finally:
            await ws.send(json.dumps({"type": "CloseStream"}))

    async def transcribe(self, audio_stream) -> str:
        headers = {"Authorization": f"Token {self.api_key}"}
        try:
            ws = await websockets.connect(self._url(),
                                          additional_headers=headers)
        except websockets.exceptions.InvalidStatus as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403):
                logger.warning("Deepgram rejected credentials (HTTP %s) — "
                               "check api_key.", status)
            raise RuntimeError(
                f"Deepgram connection failed: HTTP {status}.") from exc
        except OSError as exc:
            raise RuntimeError(f"Deepgram connection failed: {exc}") from exc

        finals = []
        sender = asyncio.create_task(self._pump(ws, audio_stream))
        try:
            async for message in ws:  # server closes after CloseStream
                if isinstance(message, (bytes, bytearray)):
                    continue
                event = json.loads(message)
                if event.get("type") == "Results" and event.get("is_final"):
                    alt = (event.get("channel", {})
                                .get("alternatives") or [{}])[0]
                    text = (alt.get("transcript") or "").strip()
                    if text:
                        finals.append(text)
        finally:
            sender.cancel()
            await ws.close()
        return " ".join(finals)
