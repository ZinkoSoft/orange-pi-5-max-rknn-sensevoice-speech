#!/usr/bin/env python3
"""
Configuration Management Module
===============================
Handles loading, validation, and management of application configuration.
"""

import os
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration with validation"""

    DEFAULT_CONFIG = {
        'sample_rate': 16000,
        'chunk_size': 1024,
        'channels': 1,
        'mel_bins': 80,
        'max_frames': 3000,
        'chunk_duration': 3.0,
        'overlap_duration': 1.5,
        'model_path': '/app/models/sensevoice-rknn/sense-voice-encoder.rknn',
        'embedding_path': '/app/models/sensevoice-rknn/embedding.npy',
        'bpe_path': '/app/models/sensevoice-rknn/chn_jpn_yue_eng_ko_spectok.bpe.model',
        'cmvn_path': '/app/models/sensevoice-rknn/am.mvn',
        'language': 'auto',
        'use_itn': True,
        'audio_device': 'default',
        'log_level': 'INFO',
        'websocket_port': 8765,
        'websocket_host': '0.0.0.0',
        'rms_margin': 0.004,
        'noise_calib_secs': 1.5,
        'min_chars': 3,
        'duplicate_cooldown_s': 4.0,
        'similarity_threshold': 0.85,  # Fuzzy matching threshold (0.0-1.0)
        'enable_vad': True,  # Enable Voice Activity Detection
        'vad_zcr_min': 0.02,  # Minimum zero-crossing rate for speech
        'vad_zcr_max': 0.35,  # Maximum zero-crossing rate for speech
        'vad_entropy_max': 0.85,  # Maximum spectral entropy for speech
        'adaptive_noise_floor': True,  # Enable adaptive noise floor updates
        'vad_mode': 'accurate',  # 'fast' (RMS+ZCR, ~0.3ms) or 'accurate' (adds FFT, ~1.5ms)
        # SenseVoice metadata filtering options
        'filter_bgm': True,  # Skip transcriptions when background music is detected
        'filter_events': [],  # List of audio events to filter out (e.g., ['BGM', 'Applause'])
        'show_emotions': False,  # Include emotion emojis in output (disabled: FP16 quantization makes SER unreliable)
        'show_events': True,  # Include event emojis in output
        'show_language': True,  # Show detected language in output
        # Language auto-locking (LID warmup)
        'enable_language_lock': True,  # Auto-lock language after warmup period
        'language_lock_warmup_s': 10.0,  # Seconds to collect LID samples before locking
        'language_lock_min_samples': 3,  # Minimum successful transcriptions before locking
        'language_lock_confidence': 0.6,  # Minimum % of samples in same language to lock
        # Confidence-gated stitching for chunk boundaries
        'enable_confidence_stitching': True,  # Use model confidence to gate chunk boundary merges
        'confidence_threshold': 0.6,  # Minimum token confidence to keep overlap tokens (0.0-1.0)
        'overlap_word_count': 4  # Number of words to track at chunk boundaries for stitching
    }

    REQUIRED_FILES = [
        'model_path',
        'embedding_path',
        'bpe_path',
        'cmvn_path'
    ]

    def __init__(self):
        self.config = {}
        self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables and defaults"""
        config = self.DEFAULT_CONFIG.copy()

        # Override with environment variables
        env_mappings = {
            'CHUNK_DURATION': ('chunk_duration', float),
            'OVERLAP_DURATION': ('overlap_duration', float),
            'MODEL_PATH': ('model_path', str),
            'EMBEDDING_PATH': ('embedding_path', str),
            'BPE_PATH': ('bpe_path', str),
            'CMVN_PATH': ('cmvn_path', str),
            'LANGUAGE': ('language', str),
            'USE_ITN': ('use_itn', lambda x: x.lower() == 'true'),
            'AUDIO_DEVICE': ('audio_device', str),
            'LOG_LEVEL': ('log_level', str),
            'WEBSOCKET_PORT': ('websocket_port', int),
            'WEBSOCKET_HOST': ('websocket_host', str),
            'RMS_MARGIN': ('rms_margin', float),
            'NOISE_CALIB_SECS': ('noise_calib_secs', float),
            'MIN_CHARS': ('min_chars', int),
            'DUPLICATE_COOLDOWN_S': ('duplicate_cooldown_s', float),
            'SIMILARITY_THRESHOLD': ('similarity_threshold', float),
            'ENABLE_VAD': ('enable_vad', lambda x: x.lower() == 'true'),
            'VAD_ZCR_MIN': ('vad_zcr_min', float),
            'VAD_ZCR_MAX': ('vad_zcr_max', float),
            'VAD_ENTROPY_MAX': ('vad_entropy_max', float),
            'ADAPTIVE_NOISE_FLOOR': ('adaptive_noise_floor', lambda x: x.lower() == 'true'),
            'VAD_MODE': ('vad_mode', str),
            'FILTER_BGM': ('filter_bgm', lambda x: x.lower() == 'true'),
            'FILTER_EVENTS': ('filter_events', lambda x: x.split(',') if x else []),
            'SHOW_EMOTIONS': ('show_emotions', lambda x: x.lower() == 'true'),
            'SHOW_EVENTS': ('show_events', lambda x: x.lower() == 'true'),
            'SHOW_LANGUAGE': ('show_language', lambda x: x.lower() == 'true'),
            'ENABLE_LANGUAGE_LOCK': ('enable_language_lock', lambda x: x.lower() == 'true'),
            'LANGUAGE_LOCK_WARMUP_S': ('language_lock_warmup_s', float),
            'LANGUAGE_LOCK_MIN_SAMPLES': ('language_lock_min_samples', int),
            'LANGUAGE_LOCK_CONFIDENCE': ('language_lock_confidence', float),
            'ENABLE_CONFIDENCE_STITCHING': ('enable_confidence_stitching', lambda x: x.lower() == 'true'),
            'CONFIDENCE_THRESHOLD': ('confidence_threshold', float),
            'OVERLAP_WORD_COUNT': ('overlap_word_count', int)
        }

        for env_var, (config_key, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    config[config_key] = converter(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value}, using default")

        self.config = config
        logger.info("✅ Configuration loaded successfully")
        return config

    def validate_config(self) -> bool:
        """Validate configuration and required files"""
        try:
            # Check required files exist
            for file_key in self.REQUIRED_FILES:
                file_path = Path(self.config[file_key])
                if not file_path.exists():
                    logger.error(f"❌ Required file not found: {file_path}")
                    return False

                # Validate model file size (should be ~485MB)
                if file_key == 'model_path':
                    model_size = file_path.stat().st_size
                    expected_size = 485 * 1024 * 1024  # ~485MB
                    if abs(model_size - expected_size) > expected_size * 0.1:  # 10% tolerance
                        logger.warning(f"⚠️ Model size unexpected: {model_size / 1024 / 1024:.1f}MB")

            # Validate language
            if self.config['language'] not in ['auto', 'zh', 'en', 'yue', 'ja', 'ko', 'nospeech']:
                logger.warning(f"⚠️ Unknown language: {self.config['language']}, defaulting to 'auto'")
                self.config['language'] = 'auto'

            # Validate numeric ranges
            if not (0.1 <= self.config['chunk_duration'] <= 10.0):
                logger.warning(f"⚠️ Chunk duration out of range: {self.config['chunk_duration']}, clamping to 3.0")
                self.config['chunk_duration'] = 3.0

            if not (0.0 <= self.config['overlap_duration'] < self.config['chunk_duration']):
                logger.warning(f"⚠️ Overlap duration invalid: {self.config['overlap_duration']}, setting to {self.config['chunk_duration'] * 0.5}")
                self.config['overlap_duration'] = self.config['chunk_duration'] * 0.5

            logger.info("✅ Configuration validation passed")
            return True

        except Exception as e:
            logger.error(f"❌ Configuration validation failed: {e}")
            return False

    def get(self, key: str, default=None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self.config.copy()

    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration values"""
        self.config.update(updates)
        logger.info(f"✅ Configuration updated: {list(updates.keys())}")