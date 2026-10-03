import unittest
from voice_v2.runtime import AssistantIdentity, InputLane, VoiceRuntime, is_yield_request, parse_wake


class VoiceRuntimeTests(unittest.TestCase):
    def test_wake_identities(self):
        self.assertEqual(parse_wake("Hey Lydia, hello").identity, AssistantIdentity.LYDIA)
        self.assertEqual(parse_wake("Hey Jarvis, hello").identity, AssistantIdentity.JARVIS)

    def test_yield_requires_address(self):
        self.assertFalse(is_yield_request("keyboard clicking"))
        self.assertTrue(is_yield_request("Lydia"))
        self.assertTrue(is_yield_request("Jarvis, pause"))

    def test_duplicate_cross_lane_is_suppressed(self):
        runtime = VoiceRuntime()
        first, _ = runtime.receive("Hey Lydia, status", InputLane.BROWSER, now=100)
        second, _ = runtime.receive("Hey Lydia, status", InputLane.LOCAL, now=101)
        self.assertTrue(first)
        self.assertFalse(second)

    def test_self_echo_is_suppressed(self):
        runtime = VoiceRuntime()
        phrase = "This is a sufficiently long sentence for echo suppression testing."
        runtime.begin_speaking(phrase)
        accepted, _ = runtime.receive(phrase, InputLane.LOCAL)
        self.assertFalse(accepted)


if __name__ == "__main__":
    unittest.main()
