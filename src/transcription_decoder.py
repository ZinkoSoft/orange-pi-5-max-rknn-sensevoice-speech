#!/usr/bin/env python3
"""
Transcription Decoder Module
============================
Handles CTC decoding, text processing, and transcription output formatting.
"""

import re
from collections import deque
import numpy as np
from typing import Optional, Dict, Any
import logging
import sentencepiece as spm

logger = logging.getLogger(__name__)

class TranscriptionDecoder:
    """Handles CTC decoding and text processing for SenseVoice"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sp = None  # SentencePiece tokenizer
        self.blank_id = 0  # Blank token ID for CTC decoding
        self.last_texts = deque(maxlen=4)
        self._last_emit_ts = 0.0

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

    def decode_output(self, output_tensor: np.ndarray) -> Optional[str]:
        """
        Decode NPU output -> text with:
        - CTC argmax + collapse
        - blank-probability gate
        - meta-token stripping
        - duplicate suppression
        """
        try:
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

            # --- Duplicate suppression within a short window
            import time
            now = time.time()
            if text_clean in self.last_texts and (now - self._last_emit_ts) < self.config['duplicate_cooldown_s']:
                logger.debug(f"🔁 Suppress duplicate: '{text_clean}'")
                return None

            self.last_texts.append(text_clean)
            self._last_emit_ts = now
            logger.info(f"📝 Transcription: {text_clean}")
            return text_clean

        except Exception as e:
            logger.error(f"❌ Text decoding error: {e}")
            return None