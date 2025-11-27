"""
Core Spatial Audio DSP Engine - VivaanXMusic 3.0
HRIR Convolution, EQ, Loudness Normalization, Binaural Processing
"""

import logging
import subprocess
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import soundfile as sf
import scipy.signal as signal
from scipy.io import wavfile

from .config import (
    FFMPEG_TIMEOUT,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_CHANNELS,
    DEFAULT_BITRATE,
    DEFAULT_FORMAT,
    TARGET_LOUDNESS,
    LOUDNESS_RANGE,
    MAX_DURATION,
    MAX_FILE_SIZE,
    HRIR_KEMAR_LEFT,
    HRIR_KEMAR_RIGHT,
)
from .presets import get_preset, HRIRPreset

logger = logging.getLogger(__name__)


class SpatializeEngine:
    """Core audio DSP engine for spatialization"""
    
    def __init__(self):
        self.sample_rate = DEFAULT_SAMPLE_RATE
        self.channels = DEFAULT_CHANNELS
        self.hrir_l = None
        self.hrir_r = None
        self._load_hrir()
    
    def _load_hrir(self):
        """Load HRIR impulse responses (KEMAR dataset)"""
        try:
            if HRIR_KEMAR_LEFT.exists() and HRIR_KEMAR_RIGHT.exists():
                logger.info("🎧 Loading HRIR impulse responses...")
                self.hrir_l, sr_l = sf.read(HRIR_KEMAR_LEFT)
                self.hrir_r, sr_r = sf.read(HRIR_KEMAR_RIGHT)
                
                # Resample if needed
                if sr_l != self.sample_rate:
                    self.hrir_l = self._resample(self.hrir_l, sr_l, self.sample_rate)
                if sr_r != self.sample_rate:
                    self.hrir_r = self._resample(self.hrir_r, sr_r, self.sample_rate)
                
                logger.info(f"✅ Loaded HRIR: {len(self.hrir_l)} samples @ {self.sample_rate}Hz")
            else:
                logger.warning("⚠️ HRIR files not found - will use fallback stereo processing")
                logger.warning(f"Expected: {HRIR_KEMAR_LEFT}, {HRIR_KEMAR_RIGHT}")
        except Exception as e:
            logger.error(f"❌ Error loading HRIR: {e}")
    
    @staticmethod
    def _resample(audio: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
        """Resample audio using scipy"""
        if sr_from == sr_to:
            return audio
        
        num_samples = int(len(audio) * sr_to / sr_from)
        return signal.resample(audio, num_samples)
    
    @staticmethod
    def _calculate_loudness(audio: np.ndarray, sr: int) -> float:
        """
        Calculate integrated loudness (LUFS) - simplified EBU R128
        Full implementation would require more complex metering
        """
        try:
            # Ensure stereo
            if audio.ndim == 1:
                audio = np.stack([audio, audio], axis=1)
            
            # Highpass filter at 75Hz (EBU R128)
            sos = signal.butter(2, 75, btype='high', fs=sr, output='sos')
            
            loudness = 0.0
            for ch in range(audio.shape[1] if audio.ndim > 1 else 1):
                channel = audio[:, ch] if audio.ndim > 1 else audio
                filtered = signal.sosfilt(sos, channel)
                
                # RMS energy
                ms_energy = np.mean(filtered ** 2)
                loudness += -0.691 + 10 * np.log10(ms_energy + 1e-10)
            
            loudness /= (audio.shape[1] if audio.ndim > 1 else 1)
            return loudness
        
        except Exception as e:
            logger.warning(f"Error calculating loudness: {e}")
            return -14.0
    
    def normalize_loudness(
        self, 
        audio: np.ndarray, 
        target_loudness: float = TARGET_LOUDNESS
    ) -> np.ndarray:
        """Normalize audio to target loudness (LUFS)"""
        try:
            current_loudness = self._calculate_loudness(audio, self.sample_rate)
            gain_db = target_loudness - current_loudness
            gain_linear = 10 ** (gain_db / 20)
            
            # Apply gain with soft limiting
            normalized = audio * gain_linear
            
            # Soft saturation to prevent clipping (tanh)
            normalized = np.tanh(normalized)
            
            logger.debug(
                f"Loudness normalized: {current_loudness:.1f} LUFS → "
                f"{target_loudness:.1f} LUFS (gain: {gain_db:.1f}dB)"
            )
            return normalized
        
        except Exception as e:
            logger.error(f"Error normalizing loudness: {e}")
            return audio
    
    @staticmethod
    def _apply_eq(audio: np.ndarray, sr: int, eq_bands) -> np.ndarray:
        """Apply multiband parametric EQ"""
        if not eq_bands:
            return audio
        
        processed = audio.copy().astype(np.float64)
        
        for band in eq_bands:
            if band.gain == 0:
                continue
            
            try:
                # Design peaking filter
                w0 = 2 * np.pi * band.frequency / sr
                alpha = np.sin(w0) / (2 * band.q_factor)
                
                # Peaking EQ coefficients
                gain_linear = 10 ** (band.gain / 40)
                b = np.array([
                    1 + alpha * gain_linear,
                    -2 * np.cos(w0),
                    1 - alpha * gain_linear,
                ])
                a = np.array([
                    1 + alpha / gain_linear,
                    -2 * np.cos(w0),
                    1 - alpha / gain_linear,
                ])
                
                # Normalize
                b = b / a[0]
                a = a / a[0]
                
                # Apply filter
                processed = signal.lfilter(b, a, processed)
            
            except Exception as e:
                logger.warning(f"Error applying EQ at {band.frequency}Hz: {e}")
                continue
        
        return processed.astype(np.float32)
    
    def spatialize(
        self,
        audio: np.ndarray,
        preset: HRIRPreset,
    ) -> np.ndarray:
        """
        Apply HRIR convolution for binaural spatialization.
        Converts mono/stereo to binaural stereo output.
        """
        try:
            # Ensure mono for processing
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            
            audio = audio.astype(np.float64)
            
            # Apply EQ if specified
            if preset.use_eq and preset.eq_preset:
                audio = self._apply_eq(audio, self.sample_rate, preset.eq_preset)
                audio = audio.astype(np.float64)
            
            # HRIR convolution for binaural effect
            if self.hrir_l is not None and self.hrir_r is not None:
                logger.info("🎧 Applying HRIR convolution (binaural)...")
                
                # Convolve with left and right HRIRs
                left_channel = signal.fftconvolve(audio, self.hrir_l, mode='same')
                right_channel = signal.fftconvolve(audio, self.hrir_r, mode='same')
                
                # Apply ILD exaggeration (makes stereo wider)
                left_channel *= preset.ild_exaggeration
                right_channel /= preset.ild_exaggeration
                
                # Combine to stereo
                binaural = np.stack([left_channel, right_channel], axis=1)
            else:
                logger.warning("⚠️ No HRIR loaded - using fallback stereo processing")
                
                left_channel = audio.copy()
                right_channel = audio.copy()
                
                # Create ITD effect (Interaural Time Difference)
                itd_samples = int(0.0007 * self.sample_rate * preset.itd_exaggeration)
                if itd_samples > 0:
                    left_channel = np.concatenate([
                        np.zeros(itd_samples), 
                        left_channel[:-itd_samples]
                    ])
                
                # Apply ILD effect (Interaural Level Difference)
                left_channel *= preset.ild_exaggeration
                right_channel /= preset.ild_exaggeration
                
                binaural = np.stack([left_channel, right_channel], axis=1)
            
            # Normalize loudness per channel
            if preset.normalize_loudness:
                for i in range(binaural.shape[1]):
                    binaural[:, i] = self.normalize_loudness(
                        binaural[:, i], 
                        preset.target_loudness
                    )
            
            # Prevent clipping
            max_val = np.max(np.abs(binaural))
            if max_val > 1.0:
                binaural = binaural / max_val * 0.99
            
            logger.info(f"✅ Spatialized: {len(audio)} samples → stereo binaural")
            return binaural.astype(np.float32)
        
        except Exception as e:
            logger.error(f"❌ Error spatializing: {e}")
            # Return stereo fallback
            return np.stack([audio, audio], axis=1).astype(np.float32)
    
    @staticmethod
    def convert_to_wav(
        input_path: Path,
        output_path: Path,
        sr: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        timeout: int = FFMPEG_TIMEOUT,
    ) -> bool:
        """Convert any audio format to WAV using ffmpeg"""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(input_path),
                "-acodec", "pcm_s16le",
                "-ar", str(sr),
                "-ac", str(channels),
                "-y",
                str(output_path),
            ]
            
            result = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                check=True,
            )
            
            logger.info(f"✅ Converted to WAV: {output_path.name} ({sr}Hz, {channels}ch)")
            return True
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Conversion timeout (>{timeout}s): {input_path.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error converting audio: {e}")
            return False
    
    @staticmethod
    def encode_output(
        input_path: Path,
        output_path: Path,
        format: str = DEFAULT_FORMAT,
        bitrate: str = DEFAULT_BITRATE,
        timeout: int = FFMPEG_TIMEOUT,
    ) -> bool:
        """Encode audio to MP3/AAC/FLAC/WAV"""
        try:
            # Map format to codec
            codec_map = {
                "mp3": ("libmp3lame", "mp3"),
                "aac": ("aac", "m4a"),
                "flac": ("flac", "flac"),
                "wav": ("pcm_s16le", "wav"),
            }
            
            codec, ext = codec_map.get(format, ("libmp3lame", "mp3"))
            
            cmd = [
                "ffmpeg",
                "-i", str(input_path),
                "-codec:a", codec,
                "-b:a", bitrate,
                "-y",
                str(output_path),
            ]
            
            result = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                check=True,
            )
            
            logger.info(
                f"✅ Encoded to {format.upper()}: {output_path.name} ({bitrate})"
            )
            return True
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Encoding timeout (>{timeout}s): {input_path.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error encoding audio: {e}")
            return False
    
    @staticmethod
    def get_audio_info(audio_path: Path) -> Tuple[int, int, float]:
        """
        Get audio file info: (sample_rate, channels, duration_seconds)
        Returns (0, 0, 0.0) on error
        """
        try:
            data, sr = sf.read(audio_path)
            
            if data.ndim == 1:
                channels = 1
            else:
                channels = data.shape[1]
            
            duration = len(data) / sr
            
            return sr, channels, duration
        
        except Exception as e:
            logger.error(f"❌ Error getting audio info: {e}")
            return 0, 0, 0.0
    
    def process_audio_file(
        self,
        input_path: Path,
        output_path: Path,
        preset_name: str = "cinema",
        timeout: int = FFMPEG_TIMEOUT,
    ) -> bool:
        """
        Full audio processing pipeline:
        1. Convert to WAV 48kHz stereo
        2. Load and apply spatialization
        3. Encode to MP3
        """
        try:
            logger.info(f"🎵 Starting processing: {input_path.name} ({preset_name})")
            
            # Get preset
            preset = get_preset(preset_name)
            logger.info(f"Using preset: {preset.name}")
            
            # Step 1: Convert to WAV
            wav_path = output_path.parent / f"{output_path.stem}_temp.wav"
            logger.info("📝 Step 1/4: Converting to WAV...")
            
            if not self.convert_to_wav(
                input_path, 
                wav_path, 
                self.sample_rate, 
                self.channels, 
                timeout
            ):
                return False
            
            # Step 2: Load audio
            logger.info("📖 Step 2/4: Loading audio...")
            audio_data, sr = sf.read(wav_path)
            
            if sr != self.sample_rate:
                logger.info(f"Resampling: {sr}Hz → {self.sample_rate}Hz")
                audio_data = self._resample(audio_data, sr, self.sample_rate)
            
            # Step 3: Spatialize
            logger.info("✨ Step 3/4: Applying spatialization...")
            spatialized = self.spatialize(audio_data, preset)
            
            # Save intermediate WAV
            sf.write(wav_path, spatialized, self.sample_rate, subtype='PCM_16')
            
            # Step 4: Encode to MP3
            logger.info("🎙️ Step 4/4: Encoding to MP3...")
            if not self.encode_output(
                wav_path, 
                output_path, 
                "mp3", 
                DEFAULT_BITRATE, 
                timeout
            ):
                return False
            
            # Cleanup temp file
            wav_path.unlink(missing_ok=True)
            
            logger.info(f"✅ Processing complete: {output_path.name}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error in processing pipeline: {e}")
            # Cleanup on error
            wav_path = output_path.parent / f"{output_path.stem}_temp.wav"
            wav_path.unlink(missing_ok=True)
            return False
