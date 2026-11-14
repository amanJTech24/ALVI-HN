"""
ALVI ML - Feature Extraction Configuration
Defines all signal processing parameters, thresholds, and pipeline configurations.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FeatureConfig:
    """Immutable configuration for audio preprocessing and acoustic feature extraction."""

    # Preprocessing parameters
    target_sr: int = 16000  # Resample to 16 kHz (standard for speech analysis)
    mono: bool = True  # Average multichannel down to mono
    min_duration_seconds: float = 2.0  # Reject recordings shorter than 2.0s
    silence_rms_threshold: float = 1e-4  # Minimum RMS to classify as non-silent
    clipping_threshold: float = 0.999  # Amplitude threshold detecting digital clipping
    normalize_peak: bool = False  # Keep raw dynamics by default; optional peak scaling

    # Spectral & Framing parameters
    n_fft: int = 512  # 32 ms window at 16 kHz
    hop_length: int = 256  # 16 ms hop (50% overlap)
    n_mfcc: int = 13  # First 13 MFCC coefficients (standard for speech)

    # Pitch (Fundamental Frequency F0) estimation parameters via YIN
    pitch_frame_length: int = 1024  # 64 ms window for low-frequency resolution
    pitch_hop_length: int = 512  # 32 ms hop for pitch tracking
    fmin: float = 65.0  # Minimum frequency (C2 ~65.4 Hz)
    fmax: float = 400.0  # Maximum frequency for conversational speech (G4 ~392 Hz)
    f0_energy_threshold_ratio: float = 0.05  # Voiced frame RMS threshold relative to peak

    # Temporal & Silence Proxy parameters
    # Note: These are energy-based acoustic proxies, NOT clinically validated pause detectors.
    activity_threshold_ratio: float = 0.10  # Frame active if RMS >= 10% of 95th percentile RMS
    min_interval_duration_seconds: float = 0.15  # Minimum continuous low-energy duration (150ms)

    # Default paths
    default_data_dir: Path = Path("data/dementianet")
    default_output_dir: Path = Path("data/processed")
    features_csv_name: str = "voice_features.csv"
    errors_csv_name: str = "extraction_errors.csv"
    summary_json_name: str = "extraction_summary.json"


# Default singleton instance
DEFAULT_CONFIG = FeatureConfig()

