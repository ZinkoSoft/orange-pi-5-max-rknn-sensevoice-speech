#!/usr/bin/env python3
"""
Transcription Decoder Module
============================
Handles CTC decoding, text processing, and transcription output formatting.
Extracts rich metadata: emotions (SER), audio events (AED), and language detection (LID).
"""

import re
import hashlib
from collections import deque
import numpy as np
from typing import Optional, Dict, Any, List
import logging
import sentencepiece as spm

logger = logging.getLogger(__name__)

# SenseVoice metadata tokens
EMOTION_TAGS = {
    'HAPPY': '😊', 'SAD': '😢', 'ANGRY': '😠', 'NEUTRAL': '😐',
    'FEARFUL': '😨', 'DISGUSTED': '🤢', 'SURPRISED': '😲'
}

AUDIO_EVENT_TAGS = {
    'BGM': '🎵', 'Speech': '💬', 'Applause': '👏', 'Laughter': '😄',
    'Crying': '😭', 'Sneeze': '🤧', 'Breath': '💨', 'Cough': '🤒'
}

LANGUAGE_TAGS = {
    'zh': 'Chinese', 'en': 'English', 'ja': 'Japanese',
    'ko': 'Korean', 'yue': 'Cantonese', 'auto': 'Auto'
}


def levenshtein_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings using Levenshtein distance.
    Returns a value between 0.0 (completely different) and 1.0 (identical).
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    
    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) / max(len1, len2) > 0.5:
        # Quick reject if length difference is too large
        return 0.0
    
    # Dynamic programming for Levenshtein distance
    prev = list(range(len2 + 1))
    for i in range(len1):
        curr = [i + 1]
        for j in range(len2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (0 if s1[i] == s2[j] else 1)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    
    distance = prev[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len) if max_len > 0 else 1.0


def parse_sensevoice_tokens(text: str) -> Dict[str, Any]:
    """
    Parse SenseVoice metadata tokens from transcription.
    Extracts language (LID), emotion (SER), and audio events (AED).
    
    Returns:
        dict with keys: text, language, emotion, audio_events, raw_text
    """
    # Find all metadata tokens
    tokens = re.findall(r"<\|(.*?)\|>", text)
    
    metadata = {
        'raw_text': text,
        'text': text,
        'language': None,
        'emotion': None,
        'audio_events': [],
        'has_itn': False
    }
    
    for token in tokens:
        token_upper = token.upper()
        
        # Check for language tags
        if token in LANGUAGE_TAGS:
            metadata['language'] = LANGUAGE_TAGS[token]
            
        # Check for emotion tags (SER)
        elif token_upper in EMOTION_TAGS:
            metadata['emotion'] = token_upper
            
        # Check for audio event tags (AED)
        elif token_upper in AUDIO_EVENT_TAGS:
            metadata['audio_events'].append(token_upper)
            
        # Check for ITN flag
        elif token == 'withitn' or token == 'WITHITN':
            metadata['has_itn'] = True
    
    # Remove all metadata tokens to get clean text
    metadata['text'] = re.sub(r"<\|.*?\|>", "", text).strip()
    
    return metadata

class TranscriptionDecoder:
    """Handles CTC decoding and text processing for SenseVoice"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sp = None  # SentencePiece tokenizer
        self.blank_id = 0  # Blank token ID for CTC decoding
        self.last_texts = deque(maxlen=6)  # Increased window for better duplicate detection
        self._last_emit_ts = 0.0
        self._similarity_threshold = config.get('similarity_threshold', 0.85)  # Fuzzy matching threshold
        self._chunk_hashes = deque(maxlen=10)  # Track recent audio chunk hashes
        self._hash_to_text = {}  # Map audio hash to transcription
        
        # Confidence-gated stitching
        self._enable_confidence_stitching = config.get('enable_confidence_stitching', True)
        self._confidence_threshold = config.get('confidence_threshold', 0.6)
        self._overlap_word_count = config.get('overlap_word_count', 4)
        self._prev_chunk_tail = None  # Store (text, confidence, word_list) from previous chunk
        
        # Progressive display filtering
        self._enable_display_filter = config.get('enable_display_filter', True)
        self._min_display_words = config.get('min_display_words', 4)  # Minimum words to display
        self._display_confidence_min = config.get('display_confidence_min', 0.5)  # Min confidence to display

    def load_tokenizer(self, bpe_path: str) -> bool:
        """Load SentencePiece tokenizer"""
        try:
            from pathlib import Path
            if not Path(bpe_path).exists():
                logger.error(f"❌ BPE model not found: {bpe_path}")
                return False

            self.sp = spm.SentencePieceProcessor()
            self.sp.load(bpe_path)

            logger.info(f"✅ Tokenizer loaded successfully, vocab size: {self.sp.vocab_size()}")
            return True
        except Exception as e:
            logger.error(f"❌ Tokenizer loading failed: {e}")
            return False

    def add_audio_hash(self, audio_hash: str, transcription: Dict[str, Any]) -> None:
        """Track audio hash to prevent processing same audio chunk multiple times"""
        self._chunk_hashes.append(audio_hash)
        self._hash_to_text[audio_hash] = transcription
        
        # Clean up old mappings
        if len(self._hash_to_text) > 20:
            # Remove oldest entries
            oldest_hashes = list(self._hash_to_text.keys())[:-15]
            for h in oldest_hashes:
                self._hash_to_text.pop(h, None)

    def decode_output(self, output_tensor: np.ndarray, audio_hash: str = None) -> Optional[Dict[str, Any]]:
        """
        Decode NPU output -> structured transcription with rich metadata:
        - Audio chunk deduplication
        - CTC argmax + collapse
        - blank-probability gate
        - Confidence-gated stitching at chunk boundaries
        - SER (Speech Emotion Recognition) extraction
        - AED (Audio Event Detection) extraction
        - LID (Language Identification) extraction
        - duplicate suppression
        
        Returns:
            dict with keys: text, language, emotion, audio_events, raw_text, confidence
            or None if filtered out
        """
        try:
            # Check if we've already processed this audio chunk
            if audio_hash and audio_hash in self._chunk_hashes:
                cached_result = self._hash_to_text.get(audio_hash)
                if cached_result:
                    logger.debug(f"🔄 Skip duplicate audio chunk (hash: {audio_hash[:8]}...)")
                    return None
            
            def unique_consecutive_with_confidence(arr, probs):
                """Collapse consecutive tokens and track max confidence per unique token"""
                if len(arr) == 0:
                    return [], [], []
                
                token_ids = []
                token_confidences = []
                token_timings = []  # (start_frame, end_frame)
                i = 0
                while i < len(arr):
                    current_token = arr[i]
                    if current_token == self.blank_id:
                        i += 1
                        continue
                    
                    # Collect all consecutive occurrences of this token
                    start_frame = i
                    max_conf = probs[current_token, i]
                    j = i + 1
                    while j < len(arr) and arr[j] == current_token:
                        max_conf = max(max_conf, probs[current_token, j])
                        j += 1
                    end_frame = j
                    
                    token_ids.append(current_token)
                    token_confidences.append(float(max_conf))
                    token_timings.append((start_frame, end_frame))
                    i = j
                
                return token_ids, token_confidences, token_timings

            if output_tensor.ndim != 3:
                logger.error(f"Unexpected output tensor shape: {output_tensor.shape}")
                return None

            # logits shape [1, vocab, T]
            logits = output_tensor[0]  # [vocab, T]

            # --- Gate by blank posterior without full softmax on entire vocab
            # compute softmax across vocab (ok at this size; T is small)
            # logits are float16/32; be numerically safe
            m = np.max(logits, axis=0, keepdims=True)
            # Clip extreme values to prevent overflow/underflow
            logits_safe = np.clip(logits - m, -100, 100)
            exp = np.exp(logits_safe)
            probs = exp / np.sum(exp, axis=0, keepdims=True)          # [vocab, T]
            blank_prob = probs[self.blank_id, :]                       # [T]
            avg_blank = float(np.mean(blank_prob))
            if avg_blank > 0.97:
                logger.debug(f"🔇 Drop by blank gate (avg_blank={avg_blank:.3f})")
                return None

            # --- Argmax decode (CTC) with confidence tracking and timestamps
            ids = np.argmax(logits, axis=0)                           # [T]
            ids, confidences, timings = unique_consecutive_with_confidence(ids, probs)

            if not ids:
                return None

            # Calculate average confidence for this chunk
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0

            # Convert ids to Python list of ints for SentencePiece
            ids_list = [int(token_id) for token_id in ids]
            text = self.sp.DecodeIds(ids_list).strip()
            
            # Convert token timings to milliseconds
            # SenseVoice: 171 frames for ~5.3 seconds → ~31.25ms per frame
            frame_duration_ms = 31.25
            tokens_with_timing = []
            for token_id, conf, (start_frame, end_frame) in zip(ids_list, confidences, timings):
                tokens_with_timing.append({
                    'token_id': token_id,
                    'token_text': self.sp.IdToPiece(token_id),
                    'start_ms': start_frame * frame_duration_ms,
                    'end_ms': end_frame * frame_duration_ms,
                    'confidence': conf
                })

            # --- Parse SenseVoice metadata tokens (LID + SER + AED)
            metadata = parse_sensevoice_tokens(text)
            text_clean = metadata['text']
            
            # Debug: Log raw text to see emotion tokens
            if text != text_clean:
                logger.debug(f"🔍 Raw model output: {text}")
                logger.debug(f"🔍 Parsed metadata: {metadata}")

            # --- Require some real alphanumeric content
            alnum = re.findall(r"[A-Za-z0-9]", text_clean)
            if len(alnum) < self.config['min_chars']:
                logger.debug(f"🔇 Too little content after cleanup: '{text_clean}'")
                return None
            
            # --- Confidence-gated stitching for chunk boundaries
            if self._enable_confidence_stitching and self._prev_chunk_tail is not None:
                text_clean = self._apply_confidence_stitching(text_clean, avg_confidence)
            
            # --- Store tail of current chunk for next iteration
            if self._enable_confidence_stitching:
                self._store_chunk_tail(text_clean, avg_confidence)

            # --- Enhanced duplicate suppression with fuzzy matching
            import time
            now = time.time()
            
            # Check for exact or near-duplicate matches
            for prev_text in self.last_texts:
                similarity = levenshtein_similarity(text_clean.lower(), prev_text.lower())
                if similarity >= self._similarity_threshold:
                    time_since_last = now - self._last_emit_ts
                    if time_since_last < self.config['duplicate_cooldown_s']:
                        logger.debug(f"🔁 Suppress duplicate (similarity={similarity:.2f}): '{text_clean}'")
                        return None

            self.last_texts.append(text_clean)
            self._last_emit_ts = now
            
            # --- Convert tokens to words with timestamps
            words_with_timing = self._tokens_to_words_with_timestamps(tokens_with_timing)
            
            # --- Build rich output with metadata
            result = {
                'text': text_clean,
                'words': words_with_timing,  # NEW: Word-level timestamps
                'language': metadata['language'],
                'emotion': metadata['emotion'],
                'audio_events': metadata['audio_events'],
                'raw_text': metadata['raw_text'],
                'has_itn': metadata['has_itn'],
                'confidence': avg_confidence
            }
            
            # Log with rich metadata
            log_parts = [f"📝 {text_clean}"]
            if metadata['language']:
                log_parts.append(f"[{metadata['language']}]")
            if metadata['emotion']:
                emoji = EMOTION_TAGS.get(metadata['emotion'], '')
                log_parts.append(f"{emoji}{metadata['emotion']}")
            if metadata['audio_events']:
                events_str = ', '.join([f"{AUDIO_EVENT_TAGS.get(e, '')}{e}" for e in metadata['audio_events']])
                log_parts.append(f"[{events_str}]")
            
            logger.info(' '.join(log_parts))
            return result

        except Exception as e:
            logger.error(f"❌ Text decoding error: {e}")
            return None
    
    def _tokens_to_words_with_timestamps(self, tokens_with_timing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert SentencePiece tokens to complete words with timing information.
        
        SentencePiece uses '▁' (U+2581) to mark word boundaries.
        Merges subword tokens into complete words while preserving timing.
        
        Args:
            tokens_with_timing: List of {token_id, token_text, start_ms, end_ms, confidence}
        
        Returns:
            List of {word, start_ms, end_ms, confidence}
        """
        words_with_timing = []
        current_word_tokens = []
        current_start_ms = None
        current_end_ms = None
        current_confidences = []
        
        for token_info in tokens_with_timing:
            token_text = token_info['token_text']
            
            # SentencePiece uses ▁ to mark beginning of words
            if token_text.startswith('▁'):
                # Start of new word - finalize previous word if exists
                if current_word_tokens:
                    word_text = ''.join(current_word_tokens).replace('▁', ' ').strip()
                    if word_text and current_start_ms is not None and current_end_ms is not None:
                        words_with_timing.append({
                            'word': word_text,
                            'start_ms': current_start_ms,
                            'end_ms': current_end_ms,
                            'confidence': float(np.mean(current_confidences))
                        })
                
                # Start new word
                current_word_tokens = [token_text]
                current_start_ms = token_info['start_ms']
                current_end_ms = token_info['end_ms']
                current_confidences = [token_info['confidence']]
            else:
                # Continuation of current word (subword token)
                current_word_tokens.append(token_text)
                # Initialize timing if not set (handles first token not being word-start)
                if current_start_ms is None:
                    current_start_ms = token_info['start_ms']
                current_end_ms = token_info['end_ms']
                current_confidences.append(token_info['confidence'])
        
        # Finalize last word
        if current_word_tokens:
            word_text = ''.join(current_word_tokens).replace('▁', ' ').strip()
            if word_text and current_start_ms is not None and current_end_ms is not None:
                words_with_timing.append({
                    'word': word_text,
                    'start_ms': current_start_ms,
                    'end_ms': current_end_ms,
                    'confidence': float(np.mean(current_confidences))
                })
        
        return words_with_timing
    
    def _store_chunk_tail(self, text: str, confidence: float) -> None:
        """Store the tail words from current chunk for next boundary comparison"""
        words = text.split()
        if len(words) >= self._overlap_word_count:
            tail_words = words[-self._overlap_word_count:]
            self._prev_chunk_tail = {
                'text': ' '.join(tail_words),
                'confidence': confidence,
                'words': tail_words
            }
        else:
            # Store what we have if less than desired word count
            self._prev_chunk_tail = {
                'text': text,
                'confidence': confidence,
                'words': words
            }
    
    def _apply_confidence_stitching(self, current_text: str, current_confidence: float) -> str:
        """
        Apply confidence-gated stitching at chunk boundaries.
        
        If the previous chunk's tail had low confidence (< threshold), and it appears
        duplicated at the start of the current chunk, we trim it to prevent garbled merges.
        
        Returns:
            Cleaned text with smart boundary handling
        """
        prev_tail = self._prev_chunk_tail
        if not prev_tail:
            return current_text
        
        prev_text = prev_tail['text']
        prev_confidence = prev_tail['confidence']
        prev_words = prev_tail['words']
        
        # Split current text into words
        current_words = current_text.split()
        if not current_words:
            return current_text
        
        # Check if previous tail appears at start of current chunk
        # Look for partial or full matches
        max_overlap = min(len(prev_words), len(current_words))
        
        for overlap_len in range(max_overlap, 0, -1):
            prev_tail_subset = ' '.join(prev_words[-overlap_len:])
            current_head_subset = ' '.join(current_words[:overlap_len])
            
            # Calculate similarity between tail and head
            similarity = levenshtein_similarity(prev_tail_subset.lower(), current_head_subset.lower())
            
            if similarity >= 0.7:  # High similarity indicates overlap
                # Decision: trim if previous tail had low confidence
                if prev_confidence < self._confidence_threshold:
                    # Previous chunk tail was uncertain - trust current chunk
                    logger.debug(f"🔧 Confidence-gated trim: prev_conf={prev_confidence:.3f} < {self._confidence_threshold:.3f}, "
                               f"removing overlap: '{current_head_subset}'")
                    return ' '.join(current_words[overlap_len:])
                elif current_confidence < self._confidence_threshold:
                    # Current chunk start is uncertain - might be better to keep previous
                    logger.debug(f"🔧 Low confidence in current chunk start ({current_confidence:.3f}), keeping overlap")
                    return current_text
                else:
                    # Both have good confidence - normal duplicate suppression will handle
                    logger.debug(f"✅ Both chunks confident (prev={prev_confidence:.3f}, curr={current_confidence:.3f}), "
                               f"overlap detected but keeping current")
                    return current_text
        
        # No significant overlap detected
        return current_text