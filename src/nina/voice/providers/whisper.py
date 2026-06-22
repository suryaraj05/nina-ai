"""OpenAI Whisper STT (non-streaming, file-based). Standalone.

This is the swap demo: a developer changes one config line —
{"provider": "deepgram", ...} -> {"provider": "whisper", ...} — and nothing
else in their application changes.
"""
import asyncio
import logging

import httpx

from ..adapter import InputAdapter

logger = logging.getLogger("nina.voice.whisper")


class WhisperProvider(InputAdapter):
    def __init__(self, api_key, model="whisper-1", language=None):
        self.api_key = api_key
        self.model = model
        self.language = language

    # supports_streaming inherits the InputAdapter default: False

    async def _collect(self, audio_stream) -> bytes:
        if isinstance(audio_stream, (bytes, bytearray)):
            return bytes(audio_stream)
        if isinstance(audio_stream, asyncio.StreamReader):
            return await audio_stream.read(-1)
        buf = bytearray()
        async for chunk in audio_stream:
            buf.extend(chunk)
        return bytes(buf)

    async def transcribe(self, audio_stream) -> str:
        audio = await self._collect(audio_stream)
        form = {"model": self.model}
        if self.language:
            form["language"] = self.language
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=form,
                files={"file": ("audio.wav", audio,
                                "application/octet-stream")})
        if resp.status_code in (401, 403):
            logger.warning("Whisper rejected credentials — check api_key.")
            raise RuntimeError("Whisper transcription failed: invalid credentials.")
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Whisper transcription failed: HTTP {resp.status_code}.")
        return (resp.json().get("text") or "").strip()
