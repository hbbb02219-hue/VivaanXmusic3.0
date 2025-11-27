"""
Configuration for Spatial Audio Module in VivaanXMusic 3.0
"""

import os
from pathlib import Path

# ============================================================================
# BASE PATHS
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # Repo root
AUDIO_CACHE_DIR = BASE_DIR / "tmp" / "audio_cache"
HRIR_DIR = BASE_DIR / "VIVAANXMUSIC" / "assets" / "hrir"

# Create if missing
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
HRIR_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# AUDIO PROCESSING SETTINGS
# ============================================================================

FFMPEG_TIMEOUT = 300  # seconds (5 mins)
FFMPEG_THREADS = 4
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 2
DEFAULT_BITRATE = "320k"
DEFAULT_FORMAT = "mp3"

# Audio file upload limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_DURATION = 600  # 10 minutes
MIN_DURATION = 5  # 5 seconds

# Loudness normalization target (LUFS)
TARGET_LOUDNESS = -14.0
LOUDNESS_RANGE = 5.0

# ============================================================================
# CACHE SETTINGS
# ============================================================================

CACHE_ENABLED = True
CACHE_TTL = 86400  # 24 hours
CACHE_CHECK_INTERVAL = 1800  # Every 30 minutes
MAX_CACHE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB max cache size

# ============================================================================
# RATE LIMITING (per user)
# ============================================================================

USER_MAX_CONCURRENT = 2
USER_MAX_REQUESTS_PER_HOUR = 10
USER_RATE_LIMIT_ENABLED = True

# ============================================================================
# BOT-WIDE LIMITS
# ============================================================================

BOT_MAX_CONCURRENT_PROCESSING = 2
BOT_MAX_REQUESTS_PER_HOUR = 100

# ============================================================================
# WORKER SETTINGS
# ============================================================================

WORKER_QUEUE_MAX_SIZE = 50
WORKER_THREADS = 2
WORKER_TIMEOUT = 300  # seconds

# ============================================================================
# HRIR PATHS (KEMAR 45 elevation)
# ============================================================================

HRIR_KEMAR_LEFT = HRIR_DIR / "kemar_45_l.wav"
HRIR_KEMAR_RIGHT = HRIR_DIR / "kemar_45_r.wav"
HRIR_SAMPLE_RATE = 44100

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

LOG_LEVEL = os.getenv("SPATIALIZE_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# FEATURE FLAGS
# ============================================================================

ENABLE_VOCAL_SEPARATION = False  # Set True to enable spleeter vocal separation
ENABLE_GPU = False
ENABLE_ADVANCED_EQ = True
ENABLE_STATUS_MESSAGES = True

# ============================================================================
# PRESETS
# ============================================================================

AVAILABLE_PRESETS = [
    "cinema",
    "maxwide",
    "bassboost",
    "vocal",
    "neutral",
    "monitor",
    "club",
]

DEFAULT_PRESET = "cinema"

# ============================================================================
# DEBUG MODE
# ============================================================================

DEBUG = os.getenv("SPATIALIZE_DEBUG", "False").lower() == "true"
