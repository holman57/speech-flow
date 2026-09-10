import audioop
import math
import struct
import time
from enum import Enum
from typing import Any, Dict, List, Optional


class VADState(Enum):
    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEAKING = "speaking"
    SPEECH_END = "speech_end"


class VoiceActivityDetector:
    """Real-time Voice Activity Detection (VAD) with energy thresholding
    and customizable silence cutoff thresholds for speech-flow.
    """

    def __init__(
        self,
        energy_threshold: float = 300.0,
        silence_timeout_seconds: float = 1.5,
        min_speech_duration_seconds: float = 0.25,
        sample_rate: int = 16000,
    ):
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout_seconds
        self.min_speech_duration = min_speech_duration_seconds
        self.sample_rate = sample_rate

        self.state = VADState.SILENCE
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.total_frames_processed = 0

    def compute_energy(self, pcm_bytes: bytes, sample_width: int = 2) -> float:
        """Calculate Root-Mean-Square (RMS) audio energy."""
        if not pcm_bytes:
            return 0.0
        try:
            return float(audioop.rms(pcm_bytes, sample_width))
        except Exception:
            # Fallback pure-python RMS calculation
            count = len(pcm_bytes) // sample_width
            if count == 0:
                return 0.0
            format_char = "h" if sample_width == 2 else "b"
            shorts = struct.unpack(f"<{count}{format_char}", pcm_bytes[:count * sample_width])
            sum_squares = sum(s * s for s in shorts)
            return math.sqrt(sum_squares / count)

    def process_chunk(self, pcm_bytes: bytes, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Process an incoming audio chunk and update VAD state."""
        now = timestamp if timestamp is not None else time.time()
        self.total_frames_processed += 1
        energy = self.compute_energy(pcm_bytes)
        is_voice = energy >= self.energy_threshold

        previous_state = self.state

        if is_voice:
            self.last_speech_time = now
            if self.state in (VADState.SILENCE, VADState.SPEECH_END):
                self.state = VADState.SPEECH_START
                self.speech_start_time = now
            elif self.state == VADState.SPEECH_START:
                if (now - (self.speech_start_time or now)) >= self.min_speech_duration:
                    self.state = VADState.SPEAKING
        else:
            if self.state in (VADState.SPEECH_START, VADState.SPEAKING):
                silence_elapsed = now - (self.last_speech_time or now)
                if silence_elapsed >= self.silence_timeout:
                    self.state = VADState.SPEECH_END
            elif self.state == VADState.SPEECH_END:
                self.state = VADState.SILENCE
                self.speech_start_time = None

        speech_duration = (now - self.speech_start_time) if self.speech_start_time else 0.0

        return {
            "state": self.state.value,
            "previous_state": previous_state.value,
            "energy": round(energy, 2),
            "is_voice": is_voice,
            "speech_duration_seconds": round(speech_duration, 2),
            "timestamp": now,
        }

    def reset(self) -> None:
        """Reset internal state to silence."""
        self.state = VADState.SILENCE
        self.speech_start_time = None
        self.last_speech_time = None
