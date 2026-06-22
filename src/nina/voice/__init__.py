"""NINA voice layer — a transport adapter on top of the text-based core.

The only public export is VoiceSession. Providers are imported lazily via
nina.voice.config.build_voice_session so this import is always clean, even
when optional audio dependencies (e.g. websockets) are not installed.
"""
from .session import VoiceSession

__all__ = ["VoiceSession"]
