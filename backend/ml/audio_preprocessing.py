"""
ALVI ML - Audio Preprocessing Module
Handles audio decoding, multichannel to mono downmixing, 16 kHz resampling,
signal validation (clipping, silence, NaN checks), and metadata tracking.
"""

from dataclasses import dataclass
import io
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf

from .feature_config import DEFAULT_CONFIG, FeatureConfig

logger = logging.getLogger(__name__)


class AudioPreprocessingError(Exception):
    """Raised when an audio recording cannot be loaded or fails quality gates."""

    def __init__(self, message: str, error_type: str = "PreprocessingError"):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


@dataclass
class PreprocessedAudio:
    """Holds cleaned 1D audio waveform, target sample rate, and processing metadata."""

    y: np.ndarray
    sr: int
    metadata: Dict[str, Any]


def load_raw_audio(file_path: Path) -> Tuple[np.ndarray, int, Dict[str, Any]]:
    """
    Decodes audio file into floating point numpy array.
    First attempts soundfile for fast header inspection and decoding.
    Falls back to librosa (which utilizes audioread / ffmpeg for MP3/MP4/M4A).
    """
    p = Path(file_path)
    if not p.is_file():
        raise AudioPreprocessingError(f"Audio file does not exist: {p}", error_type="FileNotFound")

    file_size = p.stat().st_size
    if file_size == 0:
        raise AudioPreprocessingError(f"Audio file is 0 bytes (empty): {p}", error_type="EmptyFile")

    # Inspect header using soundfile if possible
    orig_info = {"format": p.suffix.lower(), "size_bytes": file_size}
    try:
        sf_info = sf.info(str(p))
        orig_sr = sf_info.samplerate
        orig_channels = sf_info.channels
        orig_duration = sf_info.duration
        orig_subtype = sf_info.subtype
        data, sr = sf.read(str(p), dtype="float32")
    except Exception as sf_err:
        # Fall back to librosa / audioread for formats like mp3/m4a
        try:
            data, sr = librosa.load(str(p), sr=None, mono=False, dtype=np.float32)
            orig_sr = int(sr)
            orig_channels = 1 if data.ndim == 1 else data.shape[0]
            orig_duration = (data.shape[-1]) / orig_sr
            orig_subtype = "LIBROSA_FALLBACK"
        except Exception as lb_err:
            # Fall back to FFmpeg subprocess pipe if available
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                try:
                    cmd = [ffmpeg_path, "-y", "-i", str(p), "-vn", "-f", "wav", "pipe:1"]
                    proc = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                    )
                    data, sr = sf.read(io.BytesIO(proc.stdout), dtype="float32")
                    orig_sr = int(sr)
                    orig_channels = 1 if data.ndim == 1 else data.shape[1]
                    orig_duration = float(len(data) / orig_sr)
                    orig_subtype = "FFMPEG_PIPE"
                except Exception as ff_err:
                    raise AudioPreprocessingError(
                        f"Failed decoding audio ({p.name}): soundfile: {sf_err}; librosa: {lb_err}; ffmpeg: {ff_err}",
                        error_type="DecodeError",
                    )
            else:
                raise AudioPreprocessingError(
                    f"Failed decoding audio ({p.name}): soundfile: {sf_err}; librosa: {lb_err}",
                    error_type="DecodeError",
                )

    orig_info.update(
        {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "original_duration_seconds": float(orig_duration),
            "original_subtype": orig_subtype,
        }
    )
    return data, orig_sr, orig_info


def convert_to_mono(data: np.ndarray) -> np.ndarray:
    """
    Converts multichannel audio array to 1D mono by averaging channels across axis.
    Supports shape (channels, samples) from librosa or (samples, channels) from soundfile.
    """
    if data.ndim == 1:
        return data
    elif data.ndim == 2:
        # If shape is (samples, channels) - soundfile style
        if data.shape[0] > data.shape[1]:
            return np.mean(data, axis=1)
        # If shape is (channels, samples) - librosa style
        else:
            return np.mean(data, axis=0)
    else:
        raise AudioPreprocessingError(
            f"Unexpected audio array dimensions: {data.shape}", error_type="InvalidDimensions"
        )


def load_and_preprocess_audio(
    file_path: Path, config: FeatureConfig = DEFAULT_CONFIG
) -> PreprocessedAudio:
    """
    Complete audio preprocessing pipeline:
    1. Loads raw audio file.
    2. Checks for NaN / Inf values in raw data.
    3. Downmixes multichannel audio to mono by averaging channels.
    4. Resamples signal to target sample rate (16,000 Hz).
    5. Checks duration against minimum threshold (default 2.0s).
    6. Measures RMS and rejects silent recordings.
    7. Detects digital clipping (samples reaching peak amplitude >= 0.999).
    8. Optionally applies peak normalization (documented).
    9. Returns clean 1D array, sample rate, and metadata.
    """
    p = Path(file_path)
    data, orig_sr, meta = load_raw_audio(p)

    # 1. NaN / Infinite values check
    if np.isnan(data).any() or np.isinf(data).any():
        raise AudioPreprocessingError(
            f"Audio contains NaN or infinite values: {p.name}", error_type="CorruptSamples"
        )

    # 2. Downmix to mono
    mono_audio = convert_to_mono(data)

    # 3. Resample to target sample rate (default 16 kHz)
    if orig_sr != config.target_sr:
        try:
            y = librosa.resample(mono_audio, orig_sr=orig_sr, target_sr=config.target_sr)
        except Exception as resample_err:
            raise AudioPreprocessingError(
                f"Resampling failed for {p.name}: {resample_err}", error_type="ResampleError"
            )
    else:
        y = mono_audio

    # Ensure float32 contiguous array
    y = np.ascontiguousarray(y, dtype=np.float32)

    # 4. Duration check
    resampled_samples = len(y)
    resampled_duration = float(resampled_samples / config.target_sr)

    if resampled_duration < config.min_duration_seconds:
        raise AudioPreprocessingError(
            f"Audio too short ({resampled_duration:.2f}s < {config.min_duration_seconds}s): {p.name}",
            error_type="ExcessivelyShort",
        )

    # 5. Energy and silence check
    rms_val = float(np.sqrt(np.mean(y**2)))
    max_amp = float(np.max(np.abs(y)))

    if rms_val < config.silence_rms_threshold or max_amp < 1e-3:
        raise AudioPreprocessingError(
            f"Audio is silent (RMS={rms_val:.6f}, MaxAmp={max_amp:.6f}): {p.name}",
            error_type="SilentRecording",
        )

    # 6. Clipping check
    is_clipped = bool(max_amp >= config.clipping_threshold)

    # 7. Normalization (optional)
    # Default is False to preserve genuine relative speech amplitude across check-ins.
    # If enabled, peak normalization scales max absolute amplitude to 0.95.
    if config.normalize_peak and max_amp > 0:
        y = y / max_amp * 0.95
        meta["normalization"] = "peak_0.95"
    else:
        meta["normalization"] = "none_raw_dynamics"

    # 8. Record metadata
    meta.update(
        {
            "target_sr": config.target_sr,
            "resampled_samples": resampled_samples,
            "resampled_duration_seconds": resampled_duration,
            "raw_rms": rms_val,
            "peak_amplitude": max_amp,
            "is_clipped": is_clipped,
        }
    )

    return PreprocessedAudio(y=y, sr=config.target_sr, metadata=meta)

