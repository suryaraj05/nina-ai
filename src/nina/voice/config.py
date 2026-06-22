"""Convenience factory. Provider modules are imported HERE, lazily, so that
`from nina.voice import VoiceSession` never fails when an optional dependency
(e.g. websockets for Deepgram) is not installed — missing deps raise at
build_voice_session() time, not import time.
"""
from .session import VoiceSession


def build_voice_session(nina_instance, session_id: str,
                        input_config: dict, output_config: dict) -> VoiceSession:
    """Build a VoiceSession from plain config dicts.

    THE ONE-LINE PROVIDER SWAP:
        input_config = {"provider": "deepgram", "api_key": DG_KEY}   # streaming
        # ... becomes ...
        input_config = {"provider": "whisper",  "api_key": OAI_KEY}  # file-based
    Nothing else in the application changes.
    """
    in_provider = input_config.get("provider")
    in_kwargs = {k: v for k, v in input_config.items() if k != "provider"}
    if in_provider == "deepgram":
        from .providers.deepgram import DeepgramProvider  # lazy: needs websockets
        input_adapter = DeepgramProvider(**in_kwargs)
    elif in_provider == "whisper":
        from .providers.whisper import WhisperProvider
        input_adapter = WhisperProvider(**in_kwargs)
    else:
        raise ValueError(f"Unknown input provider: {in_provider!r}. "
                         "Expected 'deepgram' or 'whisper'.")

    out_provider = output_config.get("provider")
    out_kwargs = {k: v for k, v in output_config.items() if k != "provider"}
    if out_provider == "elevenlabs":
        from .providers.elevenlabs import ElevenLabsProvider
        output_adapter = ElevenLabsProvider(**out_kwargs)
    else:
        raise ValueError(f"Unknown output provider: {out_provider!r}. "
                         "Expected 'elevenlabs'.")

    return VoiceSession(nina_instance, input_adapter, output_adapter, session_id)
