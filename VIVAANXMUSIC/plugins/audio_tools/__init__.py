"""
Audio Tools Plugin Module - VivaanXMusic 3.0
Spatial audio, binaural processing, and audio effects
"""

from .spatial import register_spatial_handlers

__version__ = "1.0.0"
__all__ = ["register_spatial_handlers"]

async def init_audio_tools(app):
    """Initialize all audio tools plugins"""
    try:
        register_spatial_handlers(app)
        return True
    except Exception as e:
        print(f"Error initializing audio tools: {e}")
        return False
