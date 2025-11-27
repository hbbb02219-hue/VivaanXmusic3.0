"""
Audio Utilities Module for VivaanXMusic 3.0
Spatial Audio DSP Engine + Binaural Processing
"""

from .config import (
    AUDIO_CACHE_DIR,
    HRIR_DIR,
    MAX_FILE_SIZE,
    MAX_DURATION,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_BITRATE,
    TARGET_LOUDNESS,
    CACHE_ENABLED,
    CACHE_TTL,
    USER_MAX_CONCURRENT,
    AVAILABLE_PRESETS,
    DEFAULT_PRESET
)

from .presets import PRESETS, get_preset
from .cache import AudioCache
from .engine import SpatializeEngine
from .worker import AudioWorker

__version__ = "1.0.0"
__all__ = [
    "SpatializeEngine",
    "AudioCache", 
    "AudioWorker",
    "PRESETS",
    "get_preset",
    "AUDIO_CACHE_DIR",
    "HRIR_DIR",
    "MAX_FILE_SIZE",
    "MAX_DURATION",
]

# Global instances (singleton pattern)
cache = AudioCache()
worker = AudioWorker(max_concurrent=2)
