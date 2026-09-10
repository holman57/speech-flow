import threading
import time
from typing import Any, Callable, Dict, List, Optional


class PushToTalkManager:
    """Push-to-talk controller for speech-flow. Supports system-wide trigger keys,
    hold-to-talk semantics, and programmatic audio gate hooks.
    """

    def __init__(self, hotkey: str = "space", on_press_callback: Optional[Callable] = None, on_release_callback: Optional[Callable] = None):
        self.hotkey = hotkey.lower()
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback

        self._is_active = False
        self._press_time: Optional[float] = None
        self._release_time: Optional[float] = None
        self._lock = threading.Lock()
        self._total_speech_seconds = 0.0

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._is_active

    def trigger_press(self, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Signal that push-to-talk key is engaged."""
        now = timestamp or time.time()
        with self._lock:
            if not self._is_active:
                self._is_active = True
                self._press_time = now
                if self.on_press_callback:
                    try:
                        self.on_press_callback()
                    except Exception:
                        pass
            return {
                "active": self._is_active,
                "hotkey": self.hotkey,
                "press_timestamp": self._press_time,
            }

    def trigger_release(self, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Signal that push-to-talk key has been released."""
        now = timestamp or time.time()
        with self._lock:
            duration = 0.0
            if self._is_active:
                self._is_active = False
                self._release_time = now
                if self._press_time:
                    duration = now - self._press_time
                    self._total_speech_seconds += duration
                if self.on_release_callback:
                    try:
                        self.on_release_callback()
                    except Exception:
                        pass
            return {
                "active": self._is_active,
                "hotkey": self.hotkey,
                "duration_seconds": round(duration, 2),
                "total_seconds": round(self._total_speech_seconds, 2),
            }

    def reset(self) -> None:
        with self._lock:
            self._is_active = False
            self._press_time = None
            self._release_time = None
