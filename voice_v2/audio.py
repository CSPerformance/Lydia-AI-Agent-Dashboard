from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional

from .runtime import AssistantIdentity, InputLane


@dataclass(frozen=True)
class AudioDeviceRoute:
    input_device: Optional[str] = None
    output_device: Optional[str] = None


@dataclass(frozen=True)
class TranscriptEvent:
    text: str
    lane: InputLane
    confidence: Optional[float] = None


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    identity: AssistantIdentity
    voice_profile: str


class SpeechRecognizer(Protocol):
    def transcribe(self, pcm: bytes) -> str: ...


class SpeechSynthesizer(Protocol):
    def synthesize(self, request: SpeechRequest) -> bytes: ...


class PlaybackHandle(Protocol):
    def stop(self) -> None: ...
    def is_active(self) -> bool: ...


class AudioOutput(Protocol):
    def play(self, audio: bytes, route: AudioDeviceRoute) -> PlaybackHandle: ...


class AudioInput(Protocol):
    def current_route(self) -> AudioDeviceRoute: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


class VoiceTransport(Protocol):
    def submit_text(self, text: str, *, identity: AssistantIdentity, lane: InputLane) -> str: ...
