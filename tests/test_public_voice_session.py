import unittest
from voice_v2.runtime import InputLane, VoiceRuntime
from voice_v2.session import VoiceSession


class Transport:
    def __init__(self):
        self.calls = []

    def submit_text(self, text, *, identity, lane):
        self.calls.append(text)
        return "ok"


class Synth:
    def synthesize(self, request):
        return b"audio"


class Playback:
    def __init__(self):
        self.active = True
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.active = False

    def is_active(self):
        return self.active


class Output:
    def __init__(self):
        self.handle = None

    def play(self, audio, route):
        self.handle = Playback()
        return self.handle


class VoiceSessionTests(unittest.TestCase):
    def test_wake_routes_payload(self):
        transport = Transport()
        output = Output()
        session = VoiceSession(
            runtime=VoiceRuntime(),
            transport=transport,
            synthesizer=Synth(),
            output=output,
        )
        result = session.receive_text("Hey Lydia, status", InputLane.LOCAL)
        self.assertTrue(result.accepted)
        self.assertEqual(transport.calls, ["status"])

    def test_name_interrupts_playback(self):
        transport = Transport()
        output = Output()
        session = VoiceSession(
            runtime=VoiceRuntime(),
            transport=transport,
            synthesizer=Synth(),
            output=output,
        )
        session.receive_text("Hey Lydia, status", InputLane.LOCAL)
        handle = output.handle
        result = session.receive_text("Lydia", InputLane.LOCAL)
        self.assertTrue(result.interrupted)
        self.assertTrue(handle.stopped)


if __name__ == "__main__":
    unittest.main()
