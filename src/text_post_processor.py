"""
CPU-based text post-processing for clean transcription output.
Handles punctuation restoration, spell correction, and semantic refinement.
"""

from typing import Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TextPostProcessor:
    """Lightweight CPU-based text cleanup and enhancement"""
    
    def __init__(self, config: dict):
        self.config = config
        self.enable_punctuation = config.get('enable_punctuation_restoration', True)
        self.enable_spellcheck = config.get('enable_spellcheck', True)
        self.enable_semantic_refinement = config.get('enable_semantic_refinement', False)
        
        # Models (lazy loaded)
        self.punct_model = None
        self.symspell = None
        self.embedder = None
        
        self._last_sentence = ""
        
        logger.info("✅ TextPostProcessor initialized (lazy loading enabled)")
    
    def _lazy_load_punctuation(self):
        """Load punctuation restoration model on first use"""
        if self.punct_model is None and self.enable_punctuation:
            try:
                # Suppress all warnings during model loading
                import warnings
                import logging as stdlib_logging
                warnings.filterwarnings('ignore')
                
                # Save current logging level
                transformers_logger = stdlib_logging.getLogger('transformers')
                old_level = transformers_logger.level
                transformers_logger.setLevel(stdlib_logging.ERROR)
                
                from deepmultilingualpunctuation import PunctuationModel
                logger.info("⏳ Loading punctuation restoration model...")
                self.punct_model = PunctuationModel()
                logger.info("✅ Punctuation restoration model loaded (~100MB)")
                
                # Restore logging levels
                transformers_logger.setLevel(old_level)
                warnings.filterwarnings('default')
            except ImportError:
                logger.warning("⚠️ deepmultilingualpunctuation not installed - punctuation disabled")
                self.enable_punctuation = False
            except Exception as e:
                logger.error(f"❌ Failed to load punctuation model: {e}")
                self.enable_punctuation = False
    
    def _lazy_load_spellcheck(self):
        """Load spell checker on first use"""
        if self.symspell is None and self.enable_spellcheck:
            try:
                from symspellpy import SymSpell, Verbosity
                logger.info("⏳ Loading spell checker...")
                self.symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
                
                # Load dictionary
                dict_path = self.config.get(
                    'spell_dict_path', 
                    '/app/models/frequency_dictionary_en_82_765.txt'
                )
                
                dict_path_obj = Path(dict_path)
                if dict_path_obj.exists():
                    self.symspell.load_dictionary(str(dict_path_obj), term_index=0, count_index=1)
                    logger.info(f"✅ Spell checker loaded from {dict_path}")
                else:
                    logger.warning(f"⚠️ Spell dictionary not found: {dict_path} - spell check disabled")
                    self.symspell = None
                    self.enable_spellcheck = False
            except ImportError:
                logger.warning("⚠️ symspellpy not installed - spell check disabled")
                self.enable_spellcheck = False
            except Exception as e:
                logger.error(f"❌ Failed to load spell checker: {e}")
                self.enable_spellcheck = False
    
    def _lazy_load_embedder(self):
        """Load semantic embedder on first use"""
        if self.embedder is None and self.enable_semantic_refinement:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("⏳ Loading semantic embedder (MiniLM)...")
                self.embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                logger.info("✅ Semantic embedder loaded (MiniLM)")
            except ImportError:
                logger.warning("⚠️ sentence-transformers not installed - semantic refinement disabled")
                self.enable_semantic_refinement = False
            except Exception as e:
                logger.error(f"❌ Failed to load embedder: {e}")
                self.enable_semantic_refinement = False
    
    def restore_punctuation(self, text: str) -> str:
        """
        Add punctuation to text.
        Expected latency: ~3-10ms per sentence
        
        Args:
            text: Raw text without punctuation
            
        Returns:
            Text with punctuation and capitalization
        """
        if not text or not self.enable_punctuation:
            return text
        
        # Lazy load on first call
        self._lazy_load_punctuation()
        if self.punct_model is None:
            return text
        
        try:
            result = self.punct_model.restore_punctuation(text)
            if result != text:
                logger.debug(f"📝 Punctuation: '{text[:50]}...' → '{result[:50]}...'")
            return result
        except Exception as e:
            logger.debug(f"⚠️ Punctuation restoration failed: {e}")
            return text
    
    def fix_spelling(self, text: str) -> str:
        """
        Fix obvious typos using dictionary lookup.
        Expected latency: <1ms per sentence
        
        Args:
            text: Text that may contain typos
            
        Returns:
            Text with spelling corrections
        """
        if not text or not self.enable_spellcheck:
            return text
        
        # Lazy load on first call
        self._lazy_load_spellcheck()
        if self.symspell is None:
            return text
        
        try:
            from symspellpy import Verbosity
            tokens = text.split()
            fixed_tokens = []
            corrections_made = []
            
            for token in tokens:
                # Skip empty, proper nouns, numbers, acronyms, punctuation
                if not token:
                    continue
                    
                # Strip trailing punctuation for checking
                trailing_punct = ''
                clean_token = token
                if token and token[-1] in '.,!?;:':
                    trailing_punct = token[-1]
                    clean_token = token[:-1]
                
                # Skip if starts with capital, has digits, or is very short
                if not clean_token or clean_token[0].isupper() or any(c.isdigit() for c in clean_token) or len(clean_token) <= 2:
                    fixed_tokens.append(token)
                    continue
                
                # Look up correction
                suggestions = self.symspell.lookup(
                    clean_token.lower(),
                    Verbosity.CLOSEST,
                    max_edit_distance=2,
                    include_unknown=True
                )
                
                if suggestions and suggestions[0].term != clean_token.lower():
                    corrected = suggestions[0].term + trailing_punct
                    corrections_made.append(f"{clean_token}→{suggestions[0].term}")
                    fixed_tokens.append(corrected)
                else:
                    fixed_tokens.append(token)
            
            result = ' '.join(fixed_tokens)
            if corrections_made:
                logger.debug(f"🔤 Spell fixes: {', '.join(corrections_made)}")
            return result
            
        except Exception as e:
            logger.debug(f"⚠️ Spell check failed: {e}")
            return text
    
    def refine_boundary(self, prev_text: str, current_text: str) -> str:
        """
        Use semantic similarity to improve boundary word choices.
        Expected latency: ~2-6ms per comparison
        
        Example: "rocky clip" vs "rocky cliff" → choose "cliff" based on context
        
        Args:
            prev_text: Previous sentence for context
            current_text: Current text to refine
            
        Returns:
            Refined text
        """
        if not self.enable_semantic_refinement or not prev_text or not current_text:
            return current_text
        
        # Lazy load on first call
        self._lazy_load_embedder()
        if self.embedder is None:
            return current_text
        
        try:
            from rapidfuzz import fuzz
            
            prev_tail = ' '.join(prev_text.split()[-6:])
            cur_head = ' '.join(current_text.split()[:6])
            
            # If overlap is low, no refinement needed
            similarity = fuzz.ratio(prev_tail.lower(), cur_head.lower())
            if similarity < 70:
                return current_text
            
            # TODO: Implement semantic comparison for boundary words
            # For now, return as-is - this is a placeholder for future enhancement
            logger.debug(f"🔍 Boundary similarity: {similarity}% (no refinement applied)")
            return current_text
            
        except ImportError:
            logger.warning("⚠️ rapidfuzz not installed - boundary refinement disabled")
            self.enable_semantic_refinement = False
            return current_text
        except Exception as e:
            logger.debug(f"⚠️ Boundary refinement failed: {e}")
            return current_text
    
    def process(self, text: str, prev_text: Optional[str] = None) -> str:
        """
        Full post-processing pipeline.
        
        Args:
            text: Raw transcribed text
            prev_text: Previous sentence for context (optional)
        
        Returns:
            Cleaned and enhanced text
        
        Expected total latency: ~5-15ms per sentence
        """
        if not text:
            return text
        
        original = text
        
        # Track timing for performance monitoring
        import time
        start = time.time()
        
        # 1. Semantic boundary refinement (if enabled and context available)
        if prev_text and self.enable_semantic_refinement:
            text = self.refine_boundary(prev_text, text)
        
        # 2. Spell correction (do before punctuation to avoid breaking new sentences)
        if self.enable_spellcheck:
            text = self.fix_spelling(text)
        
        # 3. Punctuation restoration
        if self.enable_punctuation:
            text = self.restore_punctuation(text)
        
        # Performance monitoring
        latency_ms = (time.time() - start) * 1000
        if latency_ms > 20:
            logger.warning(f"⚠️ Post-processing slow: {latency_ms:.1f}ms")
        elif latency_ms > 5:
            logger.debug(f"⏱️ Post-processing: {latency_ms:.1f}ms")
        
        # Log changes
        if text != original:
            logger.info(f"📝 Post-processed ({latency_ms:.1f}ms): '{original}' → '{text}'")
        
        self._last_sentence = text
        return text
    
    def get_status(self) -> dict:
        """Get post-processor status"""
        return {
            'punctuation_enabled': self.enable_punctuation,
            'punctuation_loaded': self.punct_model is not None,
            'spellcheck_enabled': self.enable_spellcheck,
            'spellcheck_loaded': self.symspell is not None,
            'semantic_enabled': self.enable_semantic_refinement,
            'semantic_loaded': self.embedder is not None
        }
