import time
import unittest
from speech_flow.buffer import SpeechBuffer, WordToken


class TestSpeechBuffer(unittest.TestCase):
    def setUp(self):
        self.buffer = SpeechBuffer(max_words=20, silence_timeout=0.5)

    def test_interim_update(self):
        self.buffer.update_interim("hello world")
        self.assertEqual(self.buffer.interim_text, "hello world")
        self.assertEqual(self.buffer.get_full_text(), "hello world")

    def test_append_final_phrase(self):
        tokens = self.buffer.append_final_phrase("Adrastea system check")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(self.buffer.get_word_list(), ["Adrastea", "system", "check"])
        self.assertEqual(self.buffer.get_full_text(), "Adrastea system check")
        self.assertEqual(self.buffer.interim_text, "")

    def test_metrics_calculation(self):
        self.buffer.append_final_phrase("one two three four five")
        metrics = self.buffer.get_metrics()
        self.assertEqual(metrics["word_count"], 5)
        self.assertFalse(metrics["has_interim"])

    def test_buffer_capping(self):
        small_buffer = SpeechBuffer(max_words=3)
        small_buffer.append_final_phrase("one two three four five")
        self.assertEqual(len(small_buffer.tokens), 3)
        self.assertEqual(small_buffer.get_word_list(), ["three", "four", "five"])

    def test_flush_and_clear(self):
        self.buffer.append_final_phrase("wake up and report")
        flushed = self.buffer.flush()
        self.assertEqual(flushed, "wake up and report")
        self.assertEqual(len(self.buffer.tokens), 0)
        self.assertEqual(self.buffer.get_full_text(), "")

    def test_silence_detection(self):
        self.buffer.append_final_phrase("testing silence")
        self.assertFalse(self.buffer.has_silence_elapsed(threshold=1.0))
        # Simulate elapsed time
        self.buffer.last_update_time = time.time() - 2.0
        self.assertTrue(self.buffer.has_silence_elapsed(threshold=1.0))


if __name__ == "__main__":
    unittest.main()
