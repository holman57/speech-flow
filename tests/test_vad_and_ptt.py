import struct
import unittest
import time
from speech_flow.vad import VoiceActivityDetector, VADState
from speech_flow.push_to_talk import PushToTalkManager


class TestVADAndPushToTalk(unittest.TestCase):

    def setUp(self):
        self.vad = VoiceActivityDetector(energy_threshold=200.0, silence_timeout_seconds=1.0)
        self.ptt = PushToTalkManager(hotkey="space")

    def test_vad_energy_silence(self):
        # Generate 16-bit silence (zeros)
        silence_bytes = b"\x00" * 3200
        energy = self.vad.compute_energy(silence_bytes)
        self.assertEqual(energy, 0.0)

        res = self.vad.process_chunk(silence_bytes)
        self.assertEqual(res["state"], VADState.SILENCE.value)
        self.assertFalse(res["is_voice"])

    def test_vad_speech_detection_and_cutoff(self):
        # Generate high-amplitude sine wave simulating voice
        samples = [int(1500 * (1 if i % 2 == 0 else -1)) for i in range(1600)]
        voice_bytes = struct.pack(f"<{len(samples)}h", *samples)

        # 1. First chunk of voice -> SPEECH_START
        t0 = 100.0
        res1 = self.vad.process_chunk(voice_bytes, timestamp=t0)
        self.assertTrue(res1["is_voice"])
        self.assertEqual(res1["state"], VADState.SPEECH_START.value)

        # 2. Sustained voice for 0.3s -> SPEAKING
        t1 = t0 + 0.35
        res2 = self.vad.process_chunk(voice_bytes, timestamp=t1)
        self.assertEqual(res2["state"], VADState.SPEAKING.value)

        # 3. Silence for 0.5s -> Still SPEAKING (silence timeout is 1.0s)
        silence_bytes = b"\x00" * 3200
        t2 = t1 + 0.5
        res3 = self.vad.process_chunk(silence_bytes, timestamp=t2)
        self.assertEqual(res3["state"], VADState.SPEAKING.value)

        # 4. Silence for 1.2s -> SPEECH_END
        t3 = t1 + 1.2
        res4 = self.vad.process_chunk(silence_bytes, timestamp=t3)
        self.assertEqual(res4["state"], VADState.SPEECH_END.value)

    def test_push_to_talk_lifecycle(self):
        self.assertFalse(self.ptt.is_active)

        press_info = self.ptt.trigger_press(timestamp=100.0)
        self.assertTrue(press_info["active"])
        self.assertTrue(self.ptt.is_active)

        release_info = self.ptt.trigger_release(timestamp=102.5)
        self.assertFalse(release_info["active"])
        self.assertFalse(self.ptt.is_active)
        self.assertEqual(release_info["duration_seconds"], 2.5)
        self.assertEqual(release_info["total_seconds"], 2.5)


if __name__ == "__main__":
    unittest.main()
