"""Voice adapter interfaces. Interfaces only — no implementation here."""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class InputAdapter(ABC):
    """Speech-to-text. Accepts an audio stream (asyncio.StreamReader, bytes,
    or an async iterator of bytes chunks) and returns the final transcript."""

    @property
    def supports_streaming(self) -> bool:
        """True if the adapter can produce partial transcripts."""
        return False

    @abstractmethod
    async def transcribe(self, audio_stream) -> str:
        """Consume the audio stream and return the transcript text."""


class OutputAdapter(ABC):
    """Text-to-speech. Returns audio as an async bytes iterator."""

    @abstractmethod
    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Implement as an async generator yielding audio chunks as they
        arrive from the TTS backend."""
