"""ElevenLabs streaming TTS. Standalone — imports nothing from NINA core.
httpx is already a NINA core dependency, so this provider costs nothing extra.
"""
import logging

import httpx

from ..adapter import OutputAdapter

logger = logging.getLogger("nina.voice.elevenlabs")


class ElevenLabsProvider(OutputAdapter):
    def __init__(self, api_key, voice_id,
                 model_id="eleven_multilingual_v2",
                 output_format="mp3_44100_128"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format

    async def synthesize(self, text: str):
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/"
               f"{self.voice_id}/stream?output_format={self.output_format}")
        headers = {"xi-api-key": self.api_key,
                   "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers,
                                     json={"text": text,
                                           "model_id": self.model_id}) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"ElevenLabs TTS failed: HTTP {resp.status_code} "
                        f"{body[:200]!r}")
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        yield chunk
