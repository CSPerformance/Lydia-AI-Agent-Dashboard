from __future__ import annotations

from typing import Callable

from .runtime import AssistantIdentity, InputLane

BrainSubmitter = Callable[[str, AssistantIdentity, InputLane], str]


class CallbackVoiceTransport:
    def __init__(self, submitter: BrainSubmitter):
        self._submitter = submitter

    def submit_text(self, text: str, *, identity: AssistantIdentity, lane: InputLane) -> str:
        return str(self._submitter(text, identity, lane) or "")
