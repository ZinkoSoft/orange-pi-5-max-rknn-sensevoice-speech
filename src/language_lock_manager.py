"""
Language Lock Manager
=====================
Manages automatic language detection and locking to optimize
transcription performance for single-language sessions.
"""

import logging
import time
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


class LanguageLockManager:
    """Handles language auto-detection and locking logic"""

    # Language name to code mapping
    LANGUAGE_CODE_MAP = {
        'Chinese': 'zh',
        'English': 'en',
        'Japanese': 'ja',
        'Korean': 'ko',
        'Cantonese': 'yue'
    }

    def __init__(self, config: dict):
        """
        Initialize language lock manager.
        
        Args:
            config: Configuration dictionary with language settings
        """
        self.config = config
        self.enabled = config.get('enable_language_lock', True)
        self.initial_language = config.get('language', 'auto')
        self.warmup_duration = config.get('language_lock_warmup_s', 10.0)
        self.min_samples = config.get('language_lock_min_samples', 3)
        self.confidence_threshold = config.get('language_lock_confidence', 0.6)
        
        # State
        self.current_language = self.initial_language
        self.locked = (self.initial_language != 'auto')  # Already locked if not auto
        self.warmup_start = None
        self.detections = []
        
        if self.enabled and not self.locked:
            logger.info(f"🌍 Language auto-lock enabled: will lock after {self.warmup_duration}s warmup")
        elif self.locked:
            logger.info(f"🔒 Language pre-locked to '{self.initial_language}'")
        else:
            logger.info("⚠️ Language auto-lock disabled")

    def start_warmup(self) -> None:
        """Start the language detection warmup period"""
        if self.enabled and not self.locked and self.warmup_start is None:
            self.warmup_start = time.time()
            logger.info("🌍 Language detection warmup started")

    def record_detection(self, language_name: str) -> None:
        """
        Record a detected language during warmup.
        
        Args:
            language_name: Full language name (e.g., 'English', 'Chinese')
        """
        if not self.enabled or self.locked:
            return
        
        # Start warmup on first detection
        if self.warmup_start is None:
            self.start_warmup()
        
        # Map language name to code
        lang_code = self.LANGUAGE_CODE_MAP.get(language_name)
        if not lang_code:
            logger.debug(f"Unknown language name: {language_name}")
            return
        
        self.detections.append(lang_code)
        
        # Check if ready to lock
        self._check_lock_conditions()

    def _check_lock_conditions(self) -> None:
        """Check if conditions are met to lock language"""
        if self.locked or not self.warmup_start:
            return
        
        # Check warmup duration
        warmup_elapsed = time.time() - self.warmup_start
        if warmup_elapsed < self.warmup_duration:
            return
        
        # Check minimum samples
        if len(self.detections) < self.min_samples:
            logger.info(f"⚠️ Insufficient samples ({len(self.detections)}/{self.min_samples}) "
                       f"after warmup, remaining in auto mode")
            self.locked = True  # Don't try again
            return
        
        # Calculate language distribution
        lang_counts = Counter(self.detections)
        total = len(self.detections)
        most_common_lang, count = lang_counts.most_common(1)[0]
        confidence = count / total
        
        # Check confidence threshold
        if confidence >= self.confidence_threshold:
            self.current_language = most_common_lang
            self.locked = True
            logger.info(f"🔒 Language LOCKED to '{most_common_lang}' "
                       f"(confidence: {confidence:.1%}, samples: {count}/{total})")
            logger.info(f"   Distribution: {dict(lang_counts)}")
        else:
            logger.info(f"⚠️ Language detection inconclusive after warmup "
                       f"(best: {most_common_lang} at {confidence:.1%}), "
                       f"remaining in auto mode")
            self.locked = True  # Don't try again

    def get_current_language(self) -> str:
        """
        Get the current language setting.
        
        Returns:
            str: Current language code ('auto', 'zh', 'en', etc.)
        """
        return self.current_language

    def is_locked(self) -> bool:
        """
        Check if language is locked.
        
        Returns:
            bool: True if locked
        """
        return self.locked

    def is_enabled(self) -> bool:
        """
        Check if language auto-lock is enabled.
        
        Returns:
            bool: True if enabled
        """
        return self.enabled

    def get_status(self) -> dict:
        """
        Get current language lock status.
        
        Returns:
            dict: Status information
        """
        status = {
            'enabled': self.enabled,
            'locked': self.locked,
            'current_language': self.current_language,
            'detections_count': len(self.detections)
        }
        
        if self.warmup_start and not self.locked:
            warmup_elapsed = time.time() - self.warmup_start
            status['warmup_progress'] = warmup_elapsed / self.warmup_duration
            status['warmup_elapsed'] = warmup_elapsed
        
        if self.detections:
            lang_counts = Counter(self.detections)
            status['language_distribution'] = dict(lang_counts)
            if lang_counts:
                most_common_lang, count = lang_counts.most_common(1)[0]
                status['leading_language'] = most_common_lang
                status['leading_confidence'] = count / len(self.detections)
        
        return status

    def reset(self) -> None:
        """Reset language lock state"""
        self.current_language = self.initial_language
        self.locked = (self.initial_language != 'auto')
        self.warmup_start = None
        self.detections = []
        logger.info("Language lock manager reset")
