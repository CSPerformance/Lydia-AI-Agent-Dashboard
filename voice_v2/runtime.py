from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
import threading
import time
from typing import Optional


class AssistantIdentity(str, Enum):
    LYDIA = "lydia"
    JARVIS = "jarvis"


class InputLane(str, Enum):
    LOCAL = "local"
    BROWSER = "browser"
    REMOTE = "remote"


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass(frozen=True)
class WakeResult:
    identity: Optional[AssistantIdentity]
    payload: str
    addressed: bool


@dataclass
class RecentUtterance:
    digest: str
    normalized: str
    lane: InputLane
    created_at: float


@dataclass
class RecentSpeech:
    normalized: str
    created_at: float


_WAKE_RE = re.compile(
    r"^\s*(?:hey\s+)?(?P<name>lydia|lidia|lydita|jarvis)\b[\s,.:;!?–—-]*(?P<payload>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_STOP_RE = re.compile(
    r"^\s*(?:please\s+)?(?:stop(?:\s+(?:speaking|talking))?|pause|hold\s+on|wait)[.!?]*\s*$",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9']+")


def normalize_text(text: str) -> str:
    return " ".join(_WORD_RE.findall(str(text or "").lower()))


def parse_wake(text: str) -> WakeResult:
    raw = str(text or "")
    match = _WAKE_RE.match(raw)
    if not match:
        return WakeResult(None, raw.strip(), False)
    spoken_name = match.group("name").lower()
    identity = AssistantIdentity.JARVIS if spoken_name == "jarvis" else AssistantIdentity.LYDIA
    return WakeResult(identity=identity, payload=match.group("payload").strip(), addressed=True)


def is_explicit_stop(text: str) -> bool:
    return bool(_STOP_RE.fullmatch(str(text or "").strip()))


def is_yield_request(text: str) -> bool:
    wake = parse_wake(text)
    if not wake.addressed:
        return False
    if not wake.payload:
        return True
    return is_explicit_stop(wake.payload)


def presentation_voice(identity: AssistantIdentity) -> str:
    return {AssistantIdentity.LYDIA: "lydia", AssistantIdentity.JARVIS: "jarvis"}[identity]


def presentation_persona(identity: AssistantIdentity) -> str:
    return {AssistantIdentity.LYDIA: "lydia", AssistantIdentity.JARVIS: "jarvis"}[identity]


class VoiceRuntime:
    DUPLICATE_WINDOW_SECONDS = 4.0
    SELF_ECHO_TTL_SECONDS = 60.0

    def __init__(self):
        self._lock = threading.RLock()
        self.state = VoiceState.IDLE
        self.identity = AssistantIdentity.LYDIA
        self._recent_inputs: list[RecentUtterance] = []
        self._recent_speech: list[RecentSpeech] = []

    def activate(self, identity: AssistantIdentity) -> None:
        with self._lock:
            self.identity = identity
            self.state = VoiceState.LISTENING

    def begin_thinking(self) -> None:
        with self._lock:
            self.state = VoiceState.THINKING

    def begin_speaking(self, text: str) -> None:
        with self._lock:
            self._remember_speech_locked(text)
            self.state = VoiceState.SPEAKING

    def finish_speaking(self) -> None:
        with self._lock:
            self.state = VoiceState.LISTENING

    def sleep(self) -> None:
        with self._lock:
            self.state = VoiceState.IDLE

    def receive(self, text: str, lane: InputLane, *, now: Optional[float] = None) -> tuple[bool, WakeResult]:
        timestamp = time.monotonic() if now is None else float(now)
        wake = parse_wake(text)
        normalized = normalize_text(text)
        if not normalized:
            return False, wake
        with self._lock:
            self._expire_locked(timestamp)
            if self._is_self_echo_locked(normalized, timestamp):
                return False, wake
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            for row in self._recent_inputs:
                if row.digest == digest and timestamp - row.created_at <= self.DUPLICATE_WINDOW_SECONDS:
                    return False, wake
            self._recent_inputs.append(RecentUtterance(digest=digest, normalized=normalized, lane=lane, created_at=timestamp))
            if wake.identity is not None:
                self.identity = wake.identity
            return True, wake

    def should_interrupt_playback(self, transcript: str) -> bool:
        with self._lock:
            if self.state is not VoiceState.SPEAKING:
                return False
        return is_yield_request(transcript)

    def presentation(self) -> dict[str, str]:
        with self._lock:
            identity = self.identity
        return {"identity": identity.value, "voice": presentation_voice(identity), "persona": presentation_persona(identity)}

    def _remember_speech_locked(self, text: str) -> None:
        normalized = normalize_text(text)
        if not normalized:
            return
        now = time.monotonic()
        self._recent_speech.append(RecentSpeech(normalized=normalized, created_at=now))
        self._expire_locked(now)

    def _is_self_echo_locked(self, normalized: str, now: float) -> bool:
        words = normalized.split()
        if len(words) < 4:
            return False
        heard = set(words)
        for row in self._recent_speech:
            if now - row.created_at > self.SELF_ECHO_TTL_SECONDS:
                continue
            spoken_words = row.normalized.split()
            spoken = set(spoken_words)
            if not spoken:
                continue
            overlap = len(heard & spoken) / max(1, len(heard))
            if normalized in row.normalized and overlap >= 0.80:
                return True
            if len(words) >= 8 and overlap >= 0.82:
                return True
        return False

    def _expire_locked(self, now: float) -> None:
        self._recent_inputs[:] = [row for row in self._recent_inputs if now - row.created_at <= self.DUPLICATE_WINDOW_SECONDS]
        self._recent_speech[:] = [row for row in self._recent_speech if now - row.created_at <= self.SELF_ECHO_TTL_SECONDS]
