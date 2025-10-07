#!/usr/bin/env python3
"""
Transcription Decoder Module
============================
Handles CTC decoding, text processing, and transcription output formatting.
"""

import re
import hashlib
from collections import deque
import numpy as np
from typing import Optional, Dict, Any
import logging
import sentencepiece as spm

logger = logging.getLogger(__name__)


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

    def add_audio_hash(self, audio_hash: str, transcription: str) -> None:
        """Track audio hash to prevent processing same audio chunk multiple times"""
        self._chunk_hashes.append(audio_hash)
        self._hash_to_text[audio_hash] = transcription
        
        # Clean up old mappings
        if len(self._hash_to_text) > 20:
            # Remove oldest entries
            oldest_hashes = list(self._hash_to_text.keys())[:-15]
            for h in oldest_hashes:
                self._hash_to_text.pop(h, None)

    def decode_output(self, output_tensor: np.ndarray, audio_hash: str = None) -> Optional[str]:
        """
        Decode NPU output -> text with:
        - Audio chunk deduplication
        - CTC argmax + collapse
        - blank-probability gate
        - meta-token stripping
        - duplicate suppression
        """
        try:
            # Check if we've already processed this audio chunk
            if audio_hash and audio_hash in self._chunk_hashes:
                cached_text = self._hash_to_text.get(audio_hash)
                if cached_text:
                    logger.debug(f"🔄 Skip duplicate audio chunk (hash: {audio_hash[:8]}...)")
                    return None
            def unique_consecutive(arr):
                if len(arr) == 0:
                    return arr
                mask = np.append([True], arr[1:] != arr[:-1])
                out = arr[mask]
                return out[out != self.blank_id].tolist()

            if output_tensor.ndim != 3:
                logger.error(f"Unexpected output tensor shape: {output_tensor.shape}")
                return None

            # logits shape [1, vocab, T]
            logits = output_tensor[0]  # [vocab, T]

            # --- Gate by blank posterior without full softmax on entire vocab
            # compute softmax across vocab (ok at this size; T is small)
            # logits are float16/32; be numerically safe
            m = np.max(logits, axis=0, keepdims=True)
            exp = np.exp(logits - m)
            probs = exp / np.sum(exp, axis=0, keepdims=True)          # [vocab, T]
            blank_prob = probs[self.blank_id, :]                       # [T]
            avg_blank = float(np.mean(blank_prob))
            if avg_blank > 0.97:
                logger.debug(f"🔇 Drop by blank gate (avg_blank={avg_blank:.3f})")
                return None

            # --- Argmax decode (CTC)
            ids = np.argmax(logits, axis=0)                           # [T]
            ids = unique_consecutive(ids)

            if not ids:
                return None

            text = self.sp.DecodeIds(ids).strip()

            # --- Strip SenseVoice meta tokens like <|en|><|BGM|><|withitn|>
            text_clean = re.sub(r"<\|.*?\|>", "", text).strip()

            # --- Require some real alphanumeric content
            alnum = re.findall(r"[A-Za-z0-9]", text_clean)
            if len(alnum) < self.config['min_chars']:
                logger.debug(f"🔇 Too little content after cleanup: '{text_clean}'")
                return None

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
            logger.info(f"📝 Transcription: {text_clean}")
            return text_clean

        except Exception as e:
            logger.error(f"❌ Text decoding error: {e}")
            return None