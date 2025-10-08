"""
Noise Floor Calibrator
======================
Manages noise floor calibration and adaptive noise floor tracking
for improved speech detection accuracy.
"""

import logging
import numpy as np
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class NoiseFloorCalibrator:
    """Handles noise floor calibration and adaptive updates"""

    def __init__(self, config: dict):
        """
        Initialize noise floor calibrator.
        
        Args:
            config: Configuration dictionary with calibration settings
        """
        self.config = config
        self.noise_calib_secs = config.get('noise_calib_secs', 1.0)
        self.noise_floor = None
        
        # Bootstrap calibration state
        self.rms_accum = []
        self.seen_for_calib = 0
        self.calib_needed = 0  # Will be set based on sample rate
        
        # Adaptive tracking state
        self.noise_floor_history = []
        self.noise_update_counter = 0
        self.noise_update_interval = 50  # Update every 50 non-speech chunks

    def set_sample_rate(self, sample_rate: int) -> None:
        """
        Set sample rate and calculate calibration sample count.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.calib_needed = int(sample_rate * self.noise_calib_secs)
        logger.info(f"Noise floor calibration: {self.noise_calib_secs}s = {self.calib_needed} samples @ {sample_rate}Hz")

    def bootstrap_calibration(self, audio_buffer: np.ndarray) -> bool:
        """
        Bootstrap noise floor calibration from initial audio samples.
        
        Args:
            audio_buffer: Current audio buffer
            
        Returns:
            bool: True if calibration complete, False if still calibrating
        """
        if self.noise_floor is not None:
            return True  # Already calibrated
        
        if self.seen_for_calib >= self.calib_needed:
            return True  # Calibration complete
        
        # Calculate RMS for calibration sample
        sample = audio_buffer[:min(len(audio_buffer), self.calib_needed)]
        rms = self._calculate_rms(sample)
        self.rms_accum.append(rms)
        self.seen_for_calib += len(sample)
        
        if self.seen_for_calib >= self.calib_needed:
            self.noise_floor = float(np.median(self.rms_accum))
            logger.info(f"✅ Calibrated noise floor = {self.noise_floor:.6f} (over {self.noise_calib_secs:.1f}s)")
            return True
        
        return False

    def update_adaptive_noise_floor(self, rms: float) -> None:
        """
        Update adaptive noise floor from non-speech segments.
        
        Args:
            rms: RMS value from current non-speech segment
        """
        if self.noise_floor is None:
            return
        
        self.noise_floor_history.append(rms)
        self.noise_update_counter += 1
        
        if self.noise_update_counter >= self.noise_update_interval:
            if len(self.noise_floor_history) >= 20:
                # Use median of recent non-speech segments
                new_noise_floor = float(np.median(self.noise_floor_history[-50:]))
                
                # Only update if change is significant (avoid micro-adjustments)
                if abs(new_noise_floor - self.noise_floor) > 0.0001:
                    logger.info(f"🔄 Updated noise floor: {self.noise_floor:.6f} → {new_noise_floor:.6f}")
                    self.noise_floor = new_noise_floor
                
                # Keep recent history
                self.noise_floor_history = self.noise_floor_history[-100:]
            
            self.noise_update_counter = 0

    def get_noise_floor(self) -> Optional[float]:
        """
        Get current noise floor value.
        
        Returns:
            float: Current noise floor or None if not calibrated
        """
        return self.noise_floor

    def is_calibrated(self) -> bool:
        """
        Check if noise floor is calibrated.
        
        Returns:
            bool: True if calibrated
        """
        return self.noise_floor is not None

    def reset(self) -> None:
        """Reset calibration state"""
        self.noise_floor = None
        self.rms_accum = []
        self.seen_for_calib = 0
        self.noise_floor_history = []
        self.noise_update_counter = 0
        logger.info("Noise floor calibration reset")

    @staticmethod
    def _calculate_rms(audio: np.ndarray) -> float:
        """
        Calculate RMS (Root Mean Square) of audio signal.
        
        Args:
            audio: Audio samples (int16 or float32)
            
        Returns:
            float: Normalized RMS value
        """
        if len(audio) == 0:
            return 0.0
        
        # Normalize int16 to float32 range [-1.0, 1.0]
        if audio.dtype == np.int16:
            x = audio.astype(np.float32) * (1.0 / 32768.0)
        else:
            x = audio.astype(np.float32)
        
        return float(np.sqrt(np.mean(x ** 2) + 1e-12))

    def get_calibration_progress(self) -> dict:
        """
        Get calibration progress information.
        
        Returns:
            dict: Calibration state
        """
        return {
            'is_calibrated': self.is_calibrated(),
            'noise_floor': self.noise_floor,
            'progress': self.seen_for_calib / self.calib_needed if self.calib_needed > 0 else 0,
            'samples_collected': self.seen_for_calib,
            'samples_needed': self.calib_needed,
            'history_size': len(self.noise_floor_history)
        }
