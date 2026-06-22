"""WebSocket voice endpoint for the ecommerce demo.

DEMONSTRATION PROTOCOL ONLY: the client signals end-of-utterance by sending a
single 0x00 byte and barge-in by sending a single 0xFF byte. A production
system would replace these markers with proper server-side VAD-based silence
detection (see VoxGraph's VAD approach as prior art) so the user never has to
signal anything explicitly.

Wire-up: add to main.py after `app = FastAPI(...)`:
    from voice_endpoint import router as voice_router
    app.include_router(voice_router)

Requires: pip install "nina-sdk[voice]" and env vars
DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID.
"""
import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nina.voice.config import build_voice_session

logger = logging.getLogger("demo.voice")
router = APIRouter()

END_OF_UTTERANCE = b"\x00"
BARGE_IN = b"\xff"

INPUT_CONFIG = {
    "provider": "deepgram",          # the one-line swap: change to "whisper"
    "api_key": os.environ.get("DEEPGRAM_API_KEY", ""),
}
OUTPUT_CONFIG = {
    "provider": "elevenlabs",
    "api_key": os.environ.get("ELEVENLABS_API_KEY", ""),
    "voice_id": os.environ.get("ELEVENLABS_VOICE_ID", ""),
}


async def _as_chunks(blob: bytes, size: int = 3200):
    for i in range(0, len(blob), size):
        yield blob[i:i + size]


async def _stream_audio(ws: WebSocket, audio_iter):
    try:
        async for chunk in audio_iter:
            await ws.send_bytes(chunk)
        await ws.send_text("AUDIO_END")
    except Exception as exc:
        logger.warning("audio streaming stopped: %s", exc)


@router.websocket("/ws/voice/{session_id}")
async def voice_ws(ws: WebSocket, session_id: str):
    # Deferred import avoids a circular import with main.py.
    from main import nina

    await ws.accept()
    voice = build_voice_session(nina, session_id, INPUT_CONFIG, OUTPUT_CONFIG)
    buffer = bytearray()
    speak_task = None
    try:
        while True:
            data = await ws.receive_bytes()
            if data == BARGE_IN:
                await voice.cancel_speak()       # stops TTS at next chunk
                continue
            if data == END_OF_UTTERANCE:
                audio = bytes(buffer)
                buffer.clear()
                if not audio:
                    continue
                if speak_task and not speak_task.done():
                    await voice.cancel_speak()
                    await speak_task
                result = await voice.turn(_as_chunks(audio))
                if "audio" not in result:        # NINA envelope error, as-is
                    await ws.send_json(result)
                    continue
                await ws.send_json({"transcript": result["transcript"],
                                    "turn": result["turn"]})
                # Stream TTS in a task so we keep receiving (for 0xFF barge-in).
                speak_task = asyncio.create_task(
                    _stream_audio(ws, result["audio"]))
                continue
            buffer.extend(data)                  # accumulate utterance audio
    except WebSocketDisconnect:
        if speak_task and not speak_task.done():
            speak_task.cancel()
        logger.info("voice session %s disconnected", session_id)
