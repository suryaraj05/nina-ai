"""VoiceSession — wraps a text-based NINA instance with voice I/O.

Failure policy mirrors NINA's P2 spirit: a failing adapter never crashes the
turn. STT failure -> empty transcript; TTS failure -> empty audio iterator.
"""
import logging

logger = logging.getLogger("nina.voice")


async def _empty_audio():
    return
    yield  # pragma: no cover — makes this an (empty) async generator


class VoiceSession:
    def __init__(self, nina_instance, input_adapter, output_adapter,
                 session_id: str):
        self.nina = nina_instance
        self.input_adapter = input_adapter
        self.output_adapter = output_adapter
        self.session_id = session_id
        self._cancelled = False

    async def listen(self, audio_stream) -> str:
        """Transcribe audio. Returns '' (and logs) on failure — never raises."""
        try:
            transcript = await self.input_adapter.transcribe(audio_stream)
            return (transcript or "").strip()
        except Exception as exc:
            logger.warning("STT failed; treating as empty transcript: %s", exc)
            return ""

    async def speak(self, text: str):
        """Async generator of audio chunks. Yields nothing (and logs) on
        failure. Stops mid-stream when cancel_speak() is called (barge-in)."""
        try:
            stream = self.output_adapter.synthesize(text)
            async for chunk in stream:
                if self._cancelled:
                    logger.info("speak() cancelled mid-stream (barge-in).")
                    return
                yield chunk
        except Exception as exc:
            logger.warning("TTS failed; yielding no audio: %s", exc)
            return

    async def cancel_speak(self):
        """Barge-in: stop the current speak() generator at the next chunk
        boundary. Resets automatically at the start of each turn()."""
        self._cancelled = True

    async def turn(self, audio_stream) -> dict:
        """Full voice turn: transcribe -> NINA chat -> synthesize."""
        self._cancelled = False                                   # reset barge-in
        transcript = await self.listen(audio_stream)              # 1
        if not transcript:                                        # 2
            return {"turn": {"naturalLanguageResponse": "",
                             "transcript_empty": True},
                    "audio": _empty_audio(),
                    "transcript": ""}
        envelope = await self.nina.chat(transcript, self.session_id)  # 3
        if not envelope["ok"]:                                    # 4
            return envelope  # envelope returned as-is per contract
        data = envelope["data"]
        text = data["naturalLanguageResponse"]                    # 5
        return {"turn": data,                                     # 6 + 7
                "audio": self.speak(text),
                "transcript": transcript}
