"""
Audio Presets for Spatialization - VivaanXMusic 3.0
Defines EQ curves and HRIR parameters for different spatial effects
"""

from dataclasses import dataclass, field
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class EQBand:
    """Single EQ band definition"""
    frequency: float  # Hz
    gain: float       # dB
    q_factor: float   # Quality factor (bandwidth)

class EQPresets:
    """Predefined multiband EQ curves for different environments"""
    
    # Cinema - Theatrical surround effect
    CINEMA_EQ = [
        EQBand(63, 2.0, 0.7),
        EQBand(125, 1.5, 0.7),
        EQBand(250, 0.5, 0.7),
        EQBand(500, -0.5, 0.7),
        EQBand(1000, 0.0, 0.7),
        EQBand(2000, 1.0, 0.7),
        EQBand(4000, 2.0, 0.7),
        EQBand(8000, 1.5, 0.7),
        EQBand(16000, 0.5, 0.7),
    ]
    
    # MaxWide - Extra-wide stereo imaging
    MAXWIDE_EQ = [
        EQBand(63, 3.0, 0.7),
        EQBand(125, 2.0, 0.7),
        EQBand(250, 0.0, 0.7),
        EQBand(500, -1.0, 0.7),
        EQBand(1000, -0.5, 0.7),
        EQBand(2000, 1.5, 0.7),
        EQBand(4000, 3.0, 0.7),
        EQBand(8000, 2.5, 0.7),
        EQBand(16000, 1.0, 0.7),
    ]
    
    # BassBoost - Enhanced low frequencies
    BASSBOOST_EQ = [
        EQBand(63, 6.0, 0.7),
        EQBand(125, 4.0, 0.7),
        EQBand(250, 2.0, 0.7),
        EQBand(500, 0.0, 0.7),
        EQBand(1000, -0.5, 0.7),
        EQBand(2000, 0.0, 0.7),
        EQBand(4000, 0.5, 0.7),
        EQBand(8000, 0.0, 0.7),
        EQBand(16000, -0.5, 0.7),
    ]
    
    # Vocal - Forward vocals, centered imaging
    VOCAL_EQ = [
        EQBand(63, -2.0, 0.7),
        EQBand(125, -1.0, 0.7),
        EQBand(250, 0.0, 0.7),
        EQBand(500, 2.0, 0.7),
        EQBand(1000, 3.0, 0.7),
        EQBand(2000, 3.5, 0.7),
        EQBand(4000, 2.0, 0.7),
        EQBand(8000, 0.5, 0.7),
        EQBand(16000, -1.0, 0.7),
    ]
    
    # Neutral - Flat reference response
    NEUTRAL_EQ = [
        EQBand(freq, 0.0, 0.7) 
        for freq in [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    ]
    
    # Monitor - Studio reference monitoring
    MONITOR_EQ = [
        EQBand(63, -1.0, 0.7),
        EQBand(125, -0.5, 0.7),
        EQBand(250, 0.0, 0.7),
        EQBand(500, 0.5, 0.7),
        EQBand(1000, 0.0, 0.7),
        EQBand(2000, -0.5, 0.7),
        EQBand(4000, 0.0, 0.7),
        EQBand(8000, -0.5, 0.7),
        EQBand(16000, -1.0, 0.7),
    ]
    
    # Club - Bright highs + powerful bass
    CLUB_EQ = [
        EQBand(63, 4.0, 0.7),
        EQBand(125, 3.0, 0.7),
        EQBand(250, 1.0, 0.7),
        EQBand(500, -2.0, 0.7),
        EQBand(1000, -2.0, 0.7),
        EQBand(2000, 0.0, 0.7),
        EQBand(4000, 3.0, 0.7),
        EQBand(8000, 3.5, 0.7),
        EQBand(16000, 2.0, 0.7),
    ]

@dataclass
class HRIRPreset:
    """Head-Related Impulse Response spatialization preset"""
    name: str
    description: str
    elevation: float = 0.0      # degrees (-90 to 90)
    azimuth: float = 0.0        # degrees (0 to 360)
    distance: float = 1.0       # meters
    ild_exaggeration: float = 1.0  # Interaural Level Difference
    itd_exaggeration: float = 1.0  # Interaural Time Difference
    use_eq: bool = True
    eq_preset: List[EQBand] = field(default_factory=list)
    normalize_loudness: bool = True
    target_loudness: float = -14.0

# ============================================================================
# PRESET DEFINITIONS
# ============================================================================

PRESETS: Dict[str, HRIRPreset] = {
    "cinema": HRIRPreset(
        name="Cinema 🎬",
        description="Theatrical surround effect for immersive listening",
        azimuth=0.0,
        elevation=15.0,
        distance=2.0,
        ild_exaggeration=1.2,
        itd_exaggeration=1.1,
        eq_preset=EQPresets.CINEMA_EQ,
    ),
    
    "maxwide": HRIRPreset(
        name="MaxWide 🌐",
        description="Extra-wide stereo imaging, extended soundfield",
        azimuth=0.0,
        elevation=0.0,
        distance=3.0,
        ild_exaggeration=1.5,
        itd_exaggeration=1.3,
        eq_preset=EQPresets.MAXWIDE_EQ,
    ),
    
    "bassboost": HRIRPreset(
        name="BassBoost 🔊",
        description="Enhanced bass response for club/dance music",
        azimuth=0.0,
        elevation=-10.0,
        distance=1.5,
        ild_exaggeration=1.0,
        itd_exaggeration=1.0,
        eq_preset=EQPresets.BASSBOOST_EQ,
    ),
    
    "vocal": HRIRPreset(
        name="Vocal 🎤",
        description="Vocal-focused with centered imaging",
        azimuth=0.0,
        elevation=0.0,
        distance=1.0,
        ild_exaggeration=0.8,
        itd_exaggeration=0.8,
        eq_preset=EQPresets.VOCAL_EQ,
    ),
    
    "neutral": HRIRPreset(
        name="Neutral ⚖️",
        description="Reference/neutral binaural spatialization",
        azimuth=0.0,
        elevation=0.0,
        distance=1.0,
        ild_exaggeration=1.0,
        itd_exaggeration=1.0,
        eq_preset=EQPresets.NEUTRAL_EQ,
    ),
    
    "monitor": HRIRPreset(
        name="Monitor 🎛️",
        description="Studio monitor simulation (reference)",
        azimuth=0.0,
        elevation=5.0,
        distance=1.2,
        ild_exaggeration=0.9,
        itd_exaggeration=0.95,
        eq_preset=EQPresets.MONITOR_EQ,
    ),
    
    "club": HRIRPreset(
        name="Club 🕺",
        description="Club sound - bright highs + powerful bass",
        azimuth=0.0,
        elevation=-15.0,
        distance=2.5,
        ild_exaggeration=1.3,
        itd_exaggeration=1.2,
        eq_preset=EQPresets.CLUB_EQ,
    ),
}

def get_preset(preset_name: str):
    """Get preset by name with fallback to default"""
    preset = PRESETS.get(preset_name.lower())
    if not preset:
        logger.warning(f"Unknown preset '{preset_name}', using 'cinema'")
        preset = PRESETS["cinema"]
    return preset

def list_presets() -> str:
    """Return formatted list of available presets"""
    lines = ["**🎵 Available Spatial Presets:**\n"]
    for key, preset in PRESETS.items():
        lines.append(f"• **/{key}** – {preset.description}")
    return "\n".join(lines)

def get_preset_help() -> str:
    """Return preset help text"""
    return (
        "**Presets Explained:**\n\n"
        "• **cinema** – Theatrical surround (movies, immersive)\n"
        "• **maxwide** – Extra-wide stereo imaging (music)\n"
        "• **bassboost** – Enhanced bass (EDM, hip-hop)\n"
        "• **vocal** – Forward vocals (podcasts, acapella)\n"
        "• **neutral** – Reference quality (mastering)\n"
        "• **monitor** – Studio monitoring (production)\n"
        "• **club** – Party/club sound (bright + bass)"
    )
