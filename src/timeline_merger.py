#!/usr/bin/env python3
"""
Timeline Merger Module
======================
Handles timeline-based merging of transcription chunks using word-level timestamps.
Eliminates overlapping duplicates by tracking global timeline and word boundaries.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TimelineMerger:
    """
    Timeline-based chunk merger using word-level timestamps.
    
    Maintains a global timeline of emitted words and merges new chunks
    intelligently based on timestamps and confidence scores.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.global_timeline = []  # List of words with timing: {word, start_ms, end_ms, confidence}
        self.last_emit_time_ms = 0.0
        
        # Configuration
        self.overlap_confidence_threshold = config.get('timeline_overlap_confidence', 0.6)
        self.min_word_confidence = config.get('timeline_min_word_confidence', 0.4)
        self.enable_confidence_replacement = config.get('timeline_confidence_replacement', True)
        
        logger.info(f"✅ TimelineMerger initialized | overlap_conf={self.overlap_confidence_threshold:.2f} | "
                   f"min_word_conf={self.min_word_confidence:.2f}")
    
    def merge_chunk(self, words_with_timing: List[Dict[str, Any]], chunk_offset_ms: float) -> List[Dict[str, Any]]:
        """
        Merge new chunk into global timeline.
        
        Args:
            words_with_timing: List of {word, start_ms, end_ms, confidence} (relative to chunk start)
            chunk_offset_ms: Global time offset for this chunk (in milliseconds)
        
        Returns:
            List of NEW words to emit (only new content, no duplicates)
        """
        if not words_with_timing:
            return []
        
        new_words = []
        replaced_count = 0
        skipped_count = 0
        
        for word_info in words_with_timing:
            # Convert to global timeline
            global_start_ms = chunk_offset_ms + word_info['start_ms']
            global_end_ms = chunk_offset_ms + word_info['end_ms']
            word_confidence = word_info['confidence']
            word_text = word_info['word']
            
            # Filter out low-confidence words
            if word_confidence < self.min_word_confidence:
                logger.debug(f"🔇 Skip low-confidence word: '{word_text}' (conf={word_confidence:.3f})")
                skipped_count += 1
                continue
            
            # Case 1: Word entirely before last emit time → already processed
            if global_end_ms <= self.last_emit_time_ms:
                logger.debug(f"⏭️ Skip already emitted: '{word_text}' (end={global_end_ms:.0f}ms < last={self.last_emit_time_ms:.0f}ms)")
                skipped_count += 1
                continue
            
            # Case 2: Word spans the boundary (overlap) → check confidence
            if global_start_ms < self.last_emit_time_ms < global_end_ms:
                if self.enable_confidence_replacement:
                    # Find overlapping word in timeline
                    replaced = self._try_replace_overlapping_word(
                        word_text, global_start_ms, global_end_ms, word_confidence
                    )
                    if replaced:
                        replaced_count += 1
                        logger.debug(f"🔄 Replaced overlapping word with higher confidence: '{word_text}'")
                        # Note: Already added to new_words in _try_replace_overlapping_word
                        continue
                else:
                    # Skip overlapping words if replacement disabled
                    logger.debug(f"⏭️ Skip overlapping word: '{word_text}' (start={global_start_ms:.0f}ms < last={self.last_emit_time_ms:.0f}ms)")
                    skipped_count += 1
                    continue
            
            # Case 3: Word starts after last emit time → new content
            if global_start_ms >= self.last_emit_time_ms:
                new_word = {
                    'word': word_text,
                    'start_ms': global_start_ms,
                    'end_ms': global_end_ms,
                    'confidence': word_confidence
                }
                new_words.append(new_word)
                self.global_timeline.append(new_word)
                self.last_emit_time_ms = max(self.last_emit_time_ms, global_end_ms)
                logger.debug(f"✅ New word: '{word_text}' ({global_start_ms:.0f}-{global_end_ms:.0f}ms, conf={word_confidence:.3f})")
        
        if new_words or replaced_count > 0:
            logger.info(f"🔀 Merged chunk: {len(new_words)} new words, {replaced_count} replaced, {skipped_count} skipped")
        
        return new_words
    
    def _try_replace_overlapping_word(self, new_word: str, start_ms: float, end_ms: float, 
                                     new_confidence: float) -> bool:
        """
        Try to replace an overlapping word in the timeline with higher confidence version.
        
        Returns:
            True if word was replaced, False otherwise
        """
        # Find words in timeline that overlap with this time range
        for i in range(len(self.global_timeline) - 1, -1, -1):
            prev_word_info = self.global_timeline[i]
            
            # Check for temporal overlap
            if (prev_word_info['start_ms'] < end_ms and prev_word_info['end_ms'] > start_ms):
                # Words overlap in time
                if new_confidence > prev_word_info['confidence'] + self.overlap_confidence_threshold:
                    # New version is significantly more confident
                    logger.debug(f"🔄 Replace '{prev_word_info['word']}' (conf={prev_word_info['confidence']:.3f}) "
                               f"with '{new_word}' (conf={new_confidence:.3f})")
                    
                    # Update timeline
                    self.global_timeline[i] = {
                        'word': new_word,
                        'start_ms': start_ms,
                        'end_ms': end_ms,
                        'confidence': new_confidence
                    }
                    
                    return True
        
        return False
    
    def get_timeline_text(self) -> str:
        """Get the complete text from the global timeline"""
        return ' '.join(word_info['word'] for word_info in self.global_timeline)
    
    def get_timeline_stats(self) -> Dict[str, Any]:
        """Get statistics about the timeline"""
        if not self.global_timeline:
            return {
                'word_count': 0,
                'duration_ms': 0,
                'avg_confidence': 0.0
            }
        
        confidences = [w['confidence'] for w in self.global_timeline]
        return {
            'word_count': len(self.global_timeline),
            'duration_ms': self.last_emit_time_ms,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
            'min_confidence': min(confidences) if confidences else 0.0,
            'max_confidence': max(confidences) if confidences else 0.0
        }
    
    def reset(self) -> None:
        """Reset the timeline (useful for new transcription sessions)"""
        word_count = len(self.global_timeline)
        self.global_timeline = []
        self.last_emit_time_ms = 0.0
        logger.info(f"🔄 Timeline reset ({word_count} words cleared)")
