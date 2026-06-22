"""Voice layer tests — both adapters mocked, no real API calls."""
import asyncio

import pytest

from nina.voice import VoiceSession
from nina.voice.config import build_voice_session


def run(coro):
    return asyncio.run(coro)


async def drain(it):
    return [c async for c in it]


class MockInput:
    def __init__(self, transcript="show me hoodies", raise_exc=False):
        self.transcript, self.raise_exc = transcript, raise_exc

    @property
    def supports_streaming(self):
        return False

    async def transcribe(self, audio_stream):
        if self.raise_exc:
            raise RuntimeError("microphone exploded")
        return self.transcript


class MockOutput:
    def __init__(self, chunks=(b"audio",), raise_exc=False):
        self.chunks, self.raise_exc = list(chunks), raise_exc

    async def synthesize(self, text):
        if self.raise_exc:
            raise RuntimeError("tts exploded")
        for c in self.chunks:
            await asyncio.sleep(0)  # yield control between chunks
            yield c


class FakeNina:
    def __init__(self):
        self.calls = []

    async def chat(self, message, session_id):
        self.calls.append((message, session_id))
        return {"ok": True,
                "data": {"turnId": "t1", "sessionId": session_id,
                         "intent": "chitchat",
                         "naturalLanguageResponse": "Here are some hoodies."},
                "error": None}


def test_full_turn():
    nina = FakeNina()
    vs = VoiceSession(nina, MockInput(), MockOutput([b"au", b"dio"]), "s1")
    result = run(vs.turn(b"\x01\x02"))
    assert result["transcript"] == "show me hoodies"
    assert result["turn"]["naturalLanguageResponse"] == "Here are some hoodies."
    assert nina.calls == [("show me hoodies", "s1")]
    assert run(drain(result["audio"])) == [b"au", b"dio"]


def test_empty_transcript_skips_chat():
    nina = FakeNina()
    vs = VoiceSession(nina, MockInput(transcript=""), MockOutput(), "s2")
    result = run(vs.turn(b"\x01"))
    assert result["turn"]["transcript_empty"] is True
    assert result["turn"]["naturalLanguageResponse"] == ""
    assert result["transcript"] == ""
    assert nina.calls == []                       # chat never called
    assert run(drain(result["audio"])) == []


def test_barge_in_stops_audio_mid_stream():
    vs = VoiceSession(FakeNina(), MockInput(),
                      MockOutput([b"a"] * 10), "s3")

    async def flow():
        gen = vs.speak("long sentence")
        first = await gen.__anext__()             # stream has started
        await vs.cancel_speak()                   # barge-in
        rest = [c async for c in gen]
        return first, rest

    first, rest = run(flow())
    assert first == b"a"
    assert rest == []                             # stopped mid-stream


def test_input_adapter_failure_is_graceful():
    nina = FakeNina()
    vs = VoiceSession(nina, MockInput(raise_exc=True), MockOutput(), "s4")
    result = run(vs.turn(b"\x01"))                # must not raise
    assert result["turn"]["transcript_empty"] is True
    assert nina.calls == []


def test_output_adapter_failure_keeps_turn_data():
    nina = FakeNina()
    vs = VoiceSession(nina, MockInput(), MockOutput(raise_exc=True), "s5")
    result = run(vs.turn(b"\x01"))                # must not raise
    assert result["turn"]["naturalLanguageResponse"] == "Here are some hoodies."
    assert run(drain(result["audio"])) == []      # empty audio, turn intact


def test_provider_swap():
    nina = FakeNina()
    out_cfg = {"provider": "elevenlabs", "api_key": "k", "voice_id": "v"}

    vs_whisper = build_voice_session(
        nina, "s6", {"provider": "whisper", "api_key": "k"}, out_cfg)
    from nina.voice.providers.whisper import WhisperProvider
    assert isinstance(vs_whisper.input_adapter, WhisperProvider)
    assert vs_whisper.input_adapter.supports_streaming is False

    pytest.importorskip("websockets")             # optional dep
    vs_deepgram = build_voice_session(
        nina, "s7", {"provider": "deepgram", "api_key": "k"}, out_cfg)
    from nina.voice.providers.deepgram import DeepgramProvider
    assert isinstance(vs_deepgram.input_adapter, DeepgramProvider)
    assert vs_deepgram.input_adapter.supports_streaming is True
