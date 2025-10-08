"""
Audio Processing Pipeline
=========================
Orchestrates the complete audio processing pipeline from raw audio
to final transcription output.
"""

import logging
import threading
import time
import hashlib
import numpy as np

logger = logging.getLogger(__name__)


class AudioProcessingPipeline:
    """Orchestrates the audio processing pipeline"""

    def __init__(self, config: dict, audio_stream_manager, noise_floor_calibrator,
                 audio_processor, model_manager, transcription_decoder,
                 language_lock_manager, transcription_formatter, 
                 timeline_merger, statistics_tracker):
        """
        Initialize audio processing pipeline.
        
        Args:
            config: Configuration dictionary
            audio_stream_manager: Audio stream manager instance
            noise_floor_calibrator: Noise floor calibrator instance
            audio_processor: Audio processor instance
            model_manager: Model manager instance
            transcription_decoder: Transcription decoder instance
            language_lock_manager: Language lock manager instance
            transcription_formatter: Transcription formatter instance
            timeline_merger: Timeline merger instance (or None)
            statistics_tracker: Statistics tracker instance
        """
        self.config = config
        self.audio_stream = audio_stream_manager
        self.noise_calibrator = noise_floor_calibrator
        self.audio_processor = audio_processor
        self.model_manager = model_manager
        self.decoder = transcription_decoder
        self.language_manager = language_lock_manager
        self.formatter = transcription_formatter
        self.timeline_merger = timeline_merger
        self.statistics = statistics_tracker
        
        # Pipeline settings
        self.chunk_duration = config['chunk_duration']
        self.overlap_duration = config['overlap_duration']
        self.enable_timeline_merging = (timeline_merger is not None)
        
        # Pipeline state
        self.worker_thread = None
        self.is_running = False
        self.chunk_counter = 0
        self.chunk_duration_ms = self.chunk_duration * 1000

    def start(self) -> bool:
        """
        Start the audio processing pipeline.
        
        Returns:
            bool: True if successful
        """
        if self.is_running:
            logger.warning("Pipeline already running")
            return False
        
        # Set sample rate for noise calibrator
        stream_info = self.audio_stream.get_stream_info()
        device_rate = stream_info['device_rate']
        self.noise_calibrator.set_sample_rate(device_rate)
        
        # Start worker thread
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_audio_worker, daemon=True)
        self.worker_thread.start()
        
        logger.info("Audio processing pipeline started")
        return True

    def stop(self) -> None:
        """Stop the audio processing pipeline"""
        if not self.is_running:
            return
        
        logger.info("Stopping audio processing pipeline...")
        self.is_running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        
        logger.info("Audio processing pipeline stopped")

    def _process_audio_worker(self) -> None:
        """
        Main audio processing worker thread.
        
        Orchestrates the complete audio processing pipeline.
        """
        audio_buffer = np.array([], dtype=np.int16)
        
        # Get stream info
        stream_info = self.audio_stream.get_stream_info()
        dev_rate = stream_info['device_rate']
        
        # Calculate buffer sizes
        buffer_size_dev = int(dev_rate * self.chunk_duration)
        overlap_size_dev = int(dev_rate * self.overlap_duration)
        
        logger.info(f"Audio pipeline worker started | Buffer: {self.chunk_duration}s | "
                   f"Overlap: {self.overlap_duration}s | dev={dev_rate}Hz → model=16000Hz")
        
        while self.is_running:
            try:
                # Get next audio chunk
                chunk = self.audio_stream.get_audio_chunk(timeout=0.1)
                if chunk is None:
                    continue
                
                audio_buffer = np.concatenate([audio_buffer, chunk])
                
                # Bootstrap noise floor calibration
                if not self.noise_calibrator.is_calibrated():
                    if self.noise_calibrator.bootstrap_calibration(audio_buffer):
                        logger.info("Noise floor calibration complete")
                    continue
                
                # Wait for full buffer
                if len(audio_buffer) < buffer_size_dev:
                    continue
                
                # Resample to model rate
                x16 = self.audio_processor.resample_to_model_rate(audio_buffer)
                
                # Voice Activity Detection
                noise_floor = self.noise_calibrator.get_noise_floor()
                is_speech, vad_metrics = self.audio_processor.is_speech_segment(x16, noise_floor)
                
                if not is_speech:
                    logger.debug(f"Skip (VAD): RMS={vad_metrics['rms']:.4f} "
                               f"ZCR={vad_metrics['zcr']:.3f} "
                               f"Entropy={vad_metrics['spectral_entropy']:.3f}")
                    
                    # Update adaptive noise floor
                    self.noise_calibrator.update_adaptive_noise_floor(vad_metrics['rms'])
                    
                    # Keep overlap
                    audio_buffer = self._keep_overlap(audio_buffer, overlap_size_dev)
                    continue
                
                logger.debug(f"✅ Speech detected: RMS={vad_metrics['rms']:.4f} "
                           f"ZCR={vad_metrics['zcr']:.3f} "
                           f"Entropy={vad_metrics['spectral_entropy']:.3f}")
                
                # Generate audio fingerprint for deduplication
                audio_hash = hashlib.md5(x16.tobytes()).hexdigest()[:16]
                
                # Start language warmup on first speech
                if self.language_manager.is_enabled() and not self.language_manager.is_locked():
                    self.language_manager.start_warmup()
                
                # Get current language
                current_language = self.language_manager.get_current_language()
                
                # Convert to features
                mel_input = self.audio_processor.audio_to_features(
                    x16, current_language, self.config['use_itn']
                )
                
                if mel_input is not None:
                    # Run inference
                    result = self._run_inference(mel_input, audio_hash)
                    
                    if result is not None:
                        # Process and emit transcription
                        self._process_transcription_result(result, audio_hash)
                
                # Keep overlap
                audio_buffer = self._keep_overlap(audio_buffer, overlap_size_dev)
                
            except Exception as e:
                logger.error(f"Audio processing error: {e}", exc_info=True)
                self.statistics.record_error()

    def _run_inference(self, mel_input: np.ndarray, audio_hash: str) -> dict:
        """
        Run NPU inference and decode output.
        
        Args:
            mel_input: Mel spectrogram input
            audio_hash: Audio fingerprint for deduplication
            
        Returns:
            dict: Transcription result or None
        """
        try:
            # Run inference
            start_time = time.time()
            npu_output = self.model_manager.run_inference(mel_input)
            inference_time = (time.time() - start_time) * 1000
            
            if npu_output is None:
                return None
            
            # Record statistics
            self.statistics.record_inference(inference_time)
            
            # Decode transcription
            result = self.decoder.decode_output(npu_output, audio_hash)
            
            if result is not None:
                # Store audio hash for deduplication
                self.decoder.add_audio_hash(audio_hash, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return None

    def _process_transcription_result(self, result: dict, audio_hash: str) -> None:
        """
        Process transcription result: language lock, filtering, merging, output.
        
        Args:
            result: Transcription result dictionary
            audio_hash: Audio fingerprint
        """
        try:
            # Handle language auto-lock
            detected_lang = result.get('language')
            if detected_lang:
                self.language_manager.record_detection(detected_lang)
            
            # Apply metadata filtering
            should_filter, filter_reason = self.formatter.check_metadata_filter(result)
            if should_filter:
                logger.debug(f"🚫 {filter_reason}: '{result['text']}'")
                self.chunk_counter += 1
                return
            
            # Process based on merging mode
            if self.enable_timeline_merging and result.get('words'):
                self._process_with_timeline_merging(result)
            else:
                self._process_with_legacy_output(result)
            
            # Increment chunk counter
            self.chunk_counter += 1
            
        except Exception as e:
            logger.error(f"Error processing transcription result: {e}")

    def _process_with_timeline_merging(self, result: dict) -> None:
        """
        Process transcription using timeline-based merging.
        
        Args:
            result: Transcription result with word timestamps
        """
        # Calculate chunk offset in global timeline
        chunk_offset_ms = self.chunk_counter * self.chunk_duration_ms
        
        # Merge chunk into timeline
        new_words = self.timeline_merger.merge_chunk(
            result['words'],
            chunk_offset_ms
        )
        
        if new_words:
            # Build display text from NEW words only
            new_text = ' '.join(w['word'] for w in new_words)
            display_text = self.formatter.format_display_text(new_text, result)
            
            # Update result with new text
            result['text'] = new_text
            
            # Emit transcription
            self.formatter.emit_transcription(display_text, result, new_words)

    def _process_with_legacy_output(self, result: dict) -> None:
        """
        Process transcription using legacy text-based output.
        
        Args:
            result: Transcription result
        """
        display_text = self.formatter.format_display_text(result['text'], result)
        self.formatter.emit_transcription(display_text, result)

    @staticmethod
    def _keep_overlap(audio_buffer: np.ndarray, overlap_size: int) -> np.ndarray:
        """
        Keep overlap samples from buffer.
        
        Args:
            audio_buffer: Current audio buffer
            overlap_size: Number of samples to keep
            
        Returns:
            np.ndarray: Overlap samples
        """
        if overlap_size > 0:
            return audio_buffer[-overlap_size:]
        return np.array([], dtype=np.int16)

    def get_pipeline_status(self) -> dict:
        """
        Get current pipeline status.
        
        Returns:
            dict: Status information
        """
        return {
            'is_running': self.is_running,
            'chunk_counter': self.chunk_counter,
            'noise_calibration': self.noise_calibrator.get_calibration_progress(),
            'language_lock': self.language_manager.get_status(),
            'timeline_merging_enabled': self.enable_timeline_merging
        }
