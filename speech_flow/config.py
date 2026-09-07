import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Configuration for Speech Flow application."""
    # Adrastea IPC Settings
    adrastea_host: str = os.getenv("ADRASTEA_IPC_HOST", "127.0.0.1")
    adrastea_port: int = int(os.getenv("ADRASTEA_IPC_PORT", "8765"))

    # Web & Streaming Server Settings
    web_host: str = os.getenv("SPEECH_FLOW_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("SPEECH_FLOW_PORT", "7860"))

    # Buffer & Audio Settings
    silence_threshold_seconds: float = float(os.getenv("SPEECH_FLOW_SILENCE_THRESHOLD", "1.5"))
    max_buffer_words: int = int(os.getenv("SPEECH_FLOW_MAX_BUFFER_WORDS", "100"))

    # Local TTS Settings (Desktop SAPI speaker playback)
    # Default is False so only the user's selected browser voice plays in Web/Mobile mode
    desktop_tts_enabled: bool = os.getenv("SPEECH_FLOW_DESKTOP_TTS", "false").lower() == "true"
    tts_enabled: bool = desktop_tts_enabled
    tts_rate: int = int(os.getenv("SPEECH_FLOW_TTS_RATE", "0"))  # -10 to 10 for SAPI

    root_dir: Path = Path(__file__).resolve().parent.parent


config = Config()
