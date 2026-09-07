import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WordToken:
    """Individual word token inside the speech buffer."""
    text: str
    timestamp: float = field(default_factory=time.time)
    is_final: bool = True
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "timestamp": self.timestamp,
            "is_final": self.is_final,
            "confidence": round(self.confidence, 2)
        }


class SpeechBuffer:
    """Maintains, formats, and visualizes rolling interpreted words from microphone input."""

    def __init__(self, max_words: int = 100, silence_timeout: float = 1.5):
        self.max_words = max_words
        self.silence_timeout = silence_timeout
        self.tokens: List[WordToken] = []
        self.interim_text: str = ""
        self.start_time: Optional[float] = None
        self.last_update_time: Optional[float] = None

    def update_interim(self, text: str) -> None:
        """Update current non-finalized hypotheses from the STT stream."""
        self.interim_text = text.strip()
        now = time.time()
        if not self.start_time:
            self.start_time = now
        self.last_update_time = now

    def append_final_phrase(self, phrase: str, confidence: float = 1.0) -> List[WordToken]:
        """Commit a finalized phrase into distinct word tokens."""
        now = time.time()
        if not self.start_time:
            self.start_time = now
        self.last_update_time = now
        self.interim_text = ""

        words = phrase.strip().split()
        added_tokens = []
        for w in words:
            clean = w.strip()
            if clean:
                token = WordToken(text=clean, timestamp=now, is_final=True, confidence=confidence)
                self.tokens.append(token)
                added_tokens.append(token)

        # Cap buffer size
        if len(self.tokens) > self.max_words:
            self.tokens = self.tokens[-self.max_words:]

        return added_tokens

    def get_full_text(self) -> str:
        """Return full concatenated text including finalized words and any active interim text."""
        final_str = " ".join(t.text for t in self.tokens)
        if self.interim_text:
            return f"{final_str} {self.interim_text}".strip()
        return final_str

    def get_word_list(self) -> List[str]:
        """Return list of all finalized words."""
        return [t.text for t in self.tokens]

    def has_silence_elapsed(self, threshold: Optional[float] = None) -> bool:
        """Check if silence has elapsed since the last speech update."""
        if not self.last_update_time or not self.tokens:
            return False
        timeout = threshold if threshold is not None else self.silence_timeout
        return (time.time() - self.last_update_time) >= timeout

    def flush(self) -> str:
        """Retrieve full finalized buffer text and reset buffer for the next utterance."""
        text = " ".join(t.text for t in self.tokens).strip()
        self.tokens.clear()
        self.interim_text = ""
        self.start_time = None
        self.last_update_time = None
        return text

    def clear(self) -> None:
        """Reset buffer completely."""
        self.tokens.clear()
        self.interim_text = ""
        self.start_time = None
        self.last_update_time = None

    def get_metrics(self) -> Dict[str, Any]:
        """Compute buffer telemetry: word count, duration, words-per-minute."""
        now = time.time()
        duration = (self.last_update_time - self.start_time) if (self.start_time and self.last_update_time) else 0.0
        word_count = len(self.tokens)
        wpm = round((word_count / (duration / 60.0)), 1) if duration > 1.0 and word_count > 0 else 0.0

        return {
            "word_count": word_count,
            "duration_seconds": round(duration, 2),
            "wpm": wpm,
            "has_interim": bool(self.interim_text),
            "idle_seconds": round(now - self.last_update_time, 2) if self.last_update_time else 0.0
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize current buffer state for real-time visualization."""
        return {
            "tokens": [t.to_dict() for t in self.tokens],
            "interim": self.interim_text,
            "full_text": self.get_full_text(),
            "metrics": self.get_metrics()
        }
