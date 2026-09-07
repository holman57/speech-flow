import logging
import threading
from typing import Optional

logger = logging.getLogger("SpeechFlow.TTS")


class LocalTTSEngine:
    """Provides natural text-to-speech audio playback on the local desktop."""

    def __init__(self, rate: int = 0, volume: int = 100):
        self.rate = rate
        self.volume = volume
        self._sapi_voice = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import win32com.client
            self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._sapi_voice.Rate = self.rate
            self._sapi_voice.Volume = self.volume
            logger.info("Initialized native Windows SAPI TTS voice.")
        except Exception as e:
            logger.warning(f"Windows SAPI voice unavailable: {e}. Will fallback to PowerShell.")
            self._sapi_voice = None

    def speak(self, text: str, block: bool = False) -> None:
        """Play text out loud through the system speakers."""
        if not text.strip():
            return

        if block:
            self._speak_internal(text)
        else:
            threading.Thread(target=self._speak_internal, args=(text,), daemon=True).start()

    def _speak_internal(self, text: str) -> None:
        safe_text = text.replace('"', '\\"').replace("'", "")
        if self._sapi_voice:
            try:
                # 1 is SVSFlagsAsync in SAPI
                self._sapi_voice.Speak(safe_text, 0)
                return
            except Exception as e:
                logger.warning(f"SAPI speak failed: {e}. Trying PowerShell...")

        # Fallback via PowerShell System.Speech
        try:
            import subprocess
            cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Rate = {self.rate}; "
                f"$synth.Speak('{safe_text}')"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=15)
        except Exception as e:
            logger.error(f"Fallback speech synthesis failed: {e}")
