"""
Preprocessing Stage
===================
Stage 1 of the pipeline: Audio preprocessing.

Responsibilities:
- Resample audio to model rate (16kHz)
- Voice Activity Detection (VAD)
- Feature extraction (mel spectrogram)
- Audio fingerprinting for deduplication

This stage is CPU-bound and runs in parallel with NPU inference.
"""

import logging
import hashlib
import numpy as np
from typing import Any, Optional, Dict
from pipeline_stage import PipelineStage

logger = logging.getLogger(__name__)


class PreprocessingStage(PipelineStage):
    """
    Preprocessing stage: Resample → VAD → Feature Extraction.
    
    Input: Raw audio buffer (device sample rate)
    Output: {
        'mel_features': np.ndarray,
        'audio_hash': str,
        'vad_metrics': dict,
        'language': str,
        'use_itn': bool
    }
    """

    def __init__(self, input_queue, output_queue, audio_processor, 
                 noise_calibrator, language_manager, config):
        """
        Initialize preprocessing stage.
        
        Args:
            input_queue: Queue receiving raw audio buffers
            output_queue: Queue sending preprocessed features
            audio_processor: AudioProcessor instance
            noise_calibrator: NoiseFloorCalibrator instance
            language_manager: LanguageLockManager instance
            config: Configuration dictionary
        """
        super().__init__("Preprocessing", input_queue, output_queue)
        
        self.audio_processor = audio_processor
        self.noise_calibrator = noise_calibrator
        self.language_manager = language_manager
        self.config = config
        
        logger.info("PreprocessingStage initialized")

    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process raw audio buffer through preprocessing pipeline.
        
        Args:
            item: {
                'audio_buffer': np.ndarray (device rate),
                'chunk_counter': int
            }
            
        Returns:
            Preprocessed features dict or None if no speech detected
        """
        try:
            audio_buffer = item['audio_buffer']
            chunk_counter = item['chunk_counter']
            
            # Step 1: Resample to model rate (16kHz)
            x16 = self.audio_processor.resample_to_model_rate(audio_buffer)
            
            # Step 2: Voice Activity Detection
            noise_floor = self.noise_calibrator.get_noise_floor()
            is_speech, vad_metrics = self.audio_processor.is_speech_segment(x16, noise_floor)
            
            if not is_speech:
                logger.debug(f"Skip (VAD): RMS={vad_metrics['rms']:.4f} "
                           f"ZCR={vad_metrics['zcr']:.3f} "
                           f"Entropy={vad_metrics['spectral_entropy']:.3f}")
                
                # Update adaptive noise floor
                self.noise_calibrator.update_adaptive_noise_floor(vad_metrics['rms'])
                
                return None  # Skip non-speech
            
            logger.debug(f"✅ Speech detected: RMS={vad_metrics['rms']:.4f} "
                       f"ZCR={vad_metrics['zcr']:.3f} "
                       f"Entropy={vad_metrics['spectral_entropy']:.3f}")
            
            # Step 3: Generate audio fingerprint for deduplication
            audio_hash = hashlib.md5(x16.tobytes()).hexdigest()[:16]
            
            # Step 4: Start language warmup on first speech
            if self.language_manager.is_enabled() and not self.language_manager.is_locked():
                self.language_manager.start_warmup()
            
            # Get current language
            current_language = self.language_manager.get_current_language()
            
            # Step 5: Convert to features (mel spectrogram)
            mel_features = self.audio_processor.audio_to_features(
                x16, current_language, self.config['use_itn']
            )
            
            if mel_features is None:
                logger.warning("Failed to extract features")
                return None
            
            # Return preprocessed data for next stage
            return {
                'mel_features': mel_features,
                'audio_hash': audio_hash,
                'vad_metrics': vad_metrics,
                'language': current_language,
                'use_itn': self.config['use_itn'],
                'chunk_counter': chunk_counter,
                'audio_x16': x16  # Keep for potential post-analysis
            }
            
        except Exception as e:
            logger.error(f"Preprocessing error: {e}", exc_info=True)
            return None
