from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .audio import AudioDeviceRoute, AudioOutput, PlaybackHandle, SpeechRequest, SpeechSynthesizer, VoiceTransport
from .runtime import AssistantIdentity, InputLane, VoiceRuntime


@dataclass
class SessionResult:
    accepted: bool
    interrupted: bool = False
    response_text: Optional[str] = None
    identity: Optional[AssistantIdentity] = None


class VoiceSession:
    def __init__(self, *, runtime: VoiceRuntime, transport: VoiceTransport, synthesizer: SpeechSynthesizer, output: AudioOutput):
        self.runtime = runtime
        self.transport = transport
        self.synthesizer = synthesizer
        self.output = output
        self._playback: Optional[PlaybackHandle] = None

    @property
    def playback_active(self) -> bool:
        return bool(self._playback and self._playback.is_active())

    def receive_text(self, text: str, lane: InputLane, *, output_route: AudioDeviceRoute = AudioDeviceRoute()) -> SessionResult:
        if self.playback_active and self.runtime.should_interrupt_playback(text):
            self._playback.stop()
            self._playback = None
            self.runtime.finish_speaking()
            wake = self.runtime.receive(text, lane)[1]
            if wake.identity is not None:
                self.runtime.activate(wake.identity)
            return SessionResult(accepted=True, interrupted=True, identity=self.runtime.identity)

        accepted, wake = self.runtime.receive(text, lane)
        if not accepted:
            return SessionResult(accepted=False, identity=self.runtime.identity)

        if wake.addressed:
            if wake.identity is not None:
                self.runtime.activate(wake.identity)
            if not wake.payload:
                return SessionResult(accepted=True, identity=self.runtime.identity)
            request_text = wake.payload
        else:
            request_text = text.strip()

        self.runtime.begin_thinking()
        response = self.transport.submit_text(request_text, identity=self.runtime.identity, lane=lane)

        if not response:
            self.runtime.finish_speaking()
            return SessionResult(accepted=True, response_text="", identity=self.runtime.identity)

        presentation = self.runtime.presentation()
        speech_request = SpeechRequest(text=response, identity=self.runtime.identity, voice_profile=presentation["voice"])
        audio = self.synthesizer.synthesize(speech_request)
        self.runtime.begin_speaking(response)
        self._playback = self.output.play(audio, output_route)
        return SessionResult(accepted=True, response_text=response, identity=self.runtime.identity)

    def finish_playback(self) -> None:
        self._playback = None
        self.runtime.finish_speaking()
