"""
Postprocessing Stage
====================
Stage 3 of the pipeline: Decode, merge, post-process, and emit.

Responsibilities:
- Decode NPU output to text
- Language lock management
- Timeline-based merging
- Text post-processing (spell check, punctuation)
- Metadata filtering
- Async emission

This stage is CPU-bound and runs in parallel with preprocessing and NPU inference.
"""

import logging
from typing import Any, Optional, Dict
from pipeline_stage import PipelineStage

logger = logging.getLogger(__name__)


class PostprocessingStage(PipelineStage):
    """
    Postprocessing stage: Decode → Merge → Post-process → Emit.
    
    Input: {
        'npu_output': np.ndarray,
        'audio_hash': str,
        'language': str,
        'use_itn': bool,
        'chunk_counter': int,
        'inference_time_ms': float
    }
    
    Output: None (emits directly via async_emitter)
    """

    def __init__(self, input_queue, transcription_decoder, language_manager,
                 timeline_merger, transcription_formatter, text_post_processor,
                 async_emitter, config):
        """
        Initialize postprocessing stage.
        
        Args:
            input_queue: Queue receiving inference results
            transcription_decoder: TranscriptionDecoder instance
            language_manager: LanguageLockManager instance
            timeline_merger: TimelineMerger instance (or None)
            transcription_formatter: TranscriptionFormatter instance
            text_post_processor: TextPostProcessor instance
            async_emitter: AsyncEmitter instance
            config: Configuration dictionary
        """
        super().__init__("Postprocessing", input_queue, output_queue=None)
        
        self.decoder = transcription_decoder
        self.language_manager = language_manager
        self.timeline_merger = timeline_merger
        self.formatter = transcription_formatter
        self.text_post_processor = text_post_processor
        self.async_emitter = async_emitter
        self.config = config
        
        self.enable_timeline_merging = (timeline_merger is not None)
        self.chunk_duration_ms = config['chunk_duration'] * 1000
        
        logger.info("PostprocessingStage initialized")

    def process(self, item: Dict[str, Any]) -> Optional[Any]:
        """
        Process inference results through postprocessing pipeline.
        
        Args:
            item: Inference results from previous stage
            
        Returns:
            None (emits via async_emitter)
        """
        try:
            npu_output = item['npu_output']
            audio_hash = item['audio_hash']
            chunk_counter = item['chunk_counter']
            
            # Step 1: Decode NPU output to text
            result = self.decoder.decode_output(npu_output, audio_hash)
            
            if result is None:
                logger.debug(f"Decoder returned None for hash {audio_hash}")
                return None
            
            # Store audio hash for deduplication
            self.decoder.add_audio_hash(audio_hash, result)
            
            # Step 2: Handle language auto-lock
            detected_lang = result.get('language')
            if detected_lang:
                self.language_manager.record_detection(detected_lang)
            
            # Step 3: Apply metadata filtering
            should_filter, filter_reason = self.formatter.check_metadata_filter(result)
            if should_filter:
                logger.debug(f"🚫 {filter_reason}: '{result['text']}'")
                return None
            
            # Step 4: Process based on merging mode
            if self.enable_timeline_merging and result.get('words'):
                self._process_with_timeline_merging(result, chunk_counter)
            else:
                self._process_with_legacy_output(result)
            
            return None  # We emit directly, don't pass to next stage
            
        except Exception as e:
            logger.error(f"Postprocessing error: {e}", exc_info=True)
            return None

    def _process_with_timeline_merging(self, result: Dict[str, Any], 
                                      chunk_counter: int) -> None:
        """
        Process transcription using timeline-based merging with post-processing.
        
        Args:
            result: Transcription result with word timestamps
            chunk_counter: Current chunk number
        """
        # Calculate chunk offset in global timeline
        chunk_offset_ms = chunk_counter * self.chunk_duration_ms
        
        # Merge chunk into timeline
        new_words = self.timeline_merger.merge_chunk(
            result['words'],
            chunk_offset_ms
        )
        
        if new_words:
            # Build display text from NEW words only
            new_text = ' '.join(w['word'] for w in new_words)
            
            # Apply text post-processing (spell check, punctuation, etc.)
            prev_text = self.text_post_processor._last_sentence if self.text_post_processor else None
            
            if self.text_post_processor:
                cleaned_text = self.text_post_processor.process(new_text, prev_text)
            else:
                cleaned_text = new_text
            
            # Update result with cleaned text
            result['text'] = cleaned_text
            
            # Emit via async emitter (non-blocking!)
            self.async_emitter.emit(cleaned_text, result, new_words)

    def _process_with_legacy_output(self, result: Dict[str, Any]) -> None:
        """
        Process transcription using legacy text-based output.
        
        Args:
            result: Transcription result
        """
        # Emit via async emitter (non-blocking!)
        self.async_emitter.emit(result['text'], result)
