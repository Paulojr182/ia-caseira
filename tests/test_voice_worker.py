import unittest
import wave

from ai.voice_worker import OpenAIVoiceWorker


class VoiceWorkerTests(unittest.TestCase):
    def test_pcm_is_wrapped_as_valid_wav(self):
        pcm = b"\x00\x00" * 1600
        wav_bytes = OpenAIVoiceWorker._pcm_to_wav(pcm)
        with wave.open(__import__("io").BytesIO(wav_bytes), "rb") as wav:
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getnframes(), 1600)

    def test_rms_of_silence_is_zero(self):
        self.assertEqual(OpenAIVoiceWorker._rms(b"\x00\x00" * 20), 0.0)


if __name__ == "__main__":
    unittest.main()
