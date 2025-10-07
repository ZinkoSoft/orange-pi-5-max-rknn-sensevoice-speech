#!/usr/bin/env python3
"""
Enhanced NPU-Accelerated SenseVoice Live Transcription
======================================================
Production-ready live transcription with NPU acceleration, caching, and monitoring.
Refactored to follow SOLID principles with modular components.
"""

import os
import sys
import time
import logging
import threading
import queue
import signal
import numpy as np
import pyaudio

# Import modular components
from config import ConfigManager
from model_manager import ModelManager
from audio_processor import AudioProcessor
from transcription_decoder import TranscriptionDecoder
from websocket_manager import WebSocketManager
from statistics_tracker import StatisticsTracker
from timeline_merger import TimelineMerger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/transcription.log')
    ]
)
logger = logging.getLogger(__name__)

class LiveTranscriber:
    """Main orchestrator for live transcription using modular components"""

    def __init__(self):
        # Initialize configuration
        self.config_manager = ConfigManager()
        if not self.config_manager.validate_config():
            raise RuntimeError("Configuration validation failed")

        self.config = self.config_manager.get_all()

        # Initialize components
        self.model_manager = ModelManager(self.config['model_path'])
        self.audio_processor = AudioProcessor(self.config)
        self.transcription_decoder = TranscriptionDecoder(self.config)
        self.websocket_manager = WebSocketManager(self.config)
        self.statistics = StatisticsTracker()
        
        # Initialize timeline merger if enabled
        self.enable_timeline_merging = self.config.get('enable_timeline_merging', True)
        if self.enable_timeline_merging:
            self.timeline_merger = TimelineMerger(self.config)
            logger.info("✅ Timeline-based merging enabled")
        else:
            self.timeline_merger = None
            logger.info("⚠️ Timeline-based merging disabled (using legacy text deduplication)")

        # Audio processing state
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.audio = None
        self.stream = None
        self.worker_thread = None
        self.device_rate = None
        self.channels = 1
        self.noise_floor = None

        # Audio settings
        self.chunk_size = self.config['chunk_size']
        self.audio_format = pyaudio.paInt16
        self.chunk_duration = self.config['chunk_duration']
        self.overlap_duration = self.config['overlap_duration']
        self.rms_margin = self.config['rms_margin']
        self.noise_calib_secs = self.config['noise_calib_secs']

        # Language auto-lock state
        self.language_lock_enabled = self.config.get('enable_language_lock', True)
        self.current_language = self.config['language']  # Start with configured language
        self.language_locked = (self.current_language != 'auto')  # Already locked if not auto
        self.language_warmup_start = None
        self.language_detections = []  # Track detected languages during warmup
        
        # Timeline tracking for chunk offsets
        self.chunk_counter = 0
        self.chunk_duration_ms = self.chunk_duration * 1000  # Convert to milliseconds
        
        logger.info("Initializing Live Transcriber with modular components")
        if self.language_lock_enabled and not self.language_locked:
            logger.info(f"🌍 Language auto-lock enabled: will lock after {self.config.get('language_lock_warmup_s', 10)}s warmup")

        # Initialize all components
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize all modular components"""
        try:
            # Initialize model
            if not self.model_manager.initialize():
                raise RuntimeError("Failed to initialize model manager")

            # Load embeddings for audio processor
            if not self.audio_processor.load_embeddings(self.config['embedding_path']):
                raise RuntimeError("Failed to load embeddings")

            # Load tokenizer for decoder
            if not self.transcription_decoder.load_tokenizer(self.config['bpe_path']):
                raise RuntimeError("Failed to load tokenizer")

            # Initialize WebSocket manager
            if not self.websocket_manager.initialize():
                logger.warning("WebSocket manager initialization failed - continuing without WebSocket support")

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            raise

    def _calibrate_noise_floor(self, timeout_s: float = 1.0) -> None:
        """Calibrate noise floor from audio queue"""
        logger.info("Calibrating noise floor stay quiet for ~1s")
        buf = []
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                buf.append(self.audio_queue.get(timeout=timeout_s))
            except queue.Empty:
                break

        if buf:
            rms = self.audio_processor.calculate_rms(np.concatenate(buf))
            self.noise_floor = rms
            logger.info(f"Noise floor: {rms:.6f} RMS")
        else:
            self.noise_floor = 1.0e-3
            logger.info(f"Noise floor fallback: {self.noise_floor:.6f} RMS")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio input callback"""
        if self.is_recording:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def _pick_stream_params(self, device_index: int) -> tuple:
        """Return supported (rate, channels) for device"""
        audio = pyaudio.PyAudio()
        try:
            rates = [16000, 48000, 44100, 32000, 22050, 8000]
            chans = [1, 2]
            for ch in chans:
                for r in rates:
                    try:
                        audio.is_format_supported(
                            r, input_device=device_index,
                            input_channels=ch, input_format=pyaudio.paInt16
                        )
                        logger.info(f"Device supports {r} Hz, {ch} ch")
                        return r, ch
                    except ValueError:
                        continue

            # Fallback to device defaults
            info = audio.get_device_info_by_index(device_index)
            r = int(info.get('defaultSampleRate', 48000))
            ch = 1 if info.get('maxInputChannels', 1) >= 1 else info.get('maxInputChannels', 1)
            logger.warning(f"Falling back to device defaults: {r} Hz, {ch} ch")
            return r, ch
        finally:
            audio.terminate()

    def _bootstrap_noise_floor(self, audio_buffer: np.ndarray, rms_accum: list, 
                               seen_for_calib: int, calib_needed: int) -> tuple:
        """
        Bootstrap noise floor calibration from initial audio samples.
        
        Args:
            audio_buffer: Current audio buffer
            rms_accum: Accumulated RMS values for calibration
            seen_for_calib: Number of samples seen so far
            calib_needed: Total samples needed for calibration
            
        Returns:
            tuple: (noise_floor, seen_for_calib) - noise_floor is None if still calibrating
        """
        sample = audio_buffer[:min(len(audio_buffer), calib_needed)]
        rms_accum.append(self.audio_processor.calculate_rms(sample))
        seen_for_calib = len(sample)
        
        if seen_for_calib >= calib_needed:
            noise_floor = float(np.median(rms_accum))
            logger.info(f"Calibrated noise floor = {noise_floor:.6f} (over {self.noise_calib_secs:.1f}s)")
            return noise_floor, seen_for_calib
        
        return None, seen_for_calib
    
    def _update_adaptive_noise_floor(self, vad_metrics: dict, noise_floor_history: list, 
                                    noise_update_counter: int, noise_update_interval: int) -> tuple:
        """
        Update adaptive noise floor from non-speech segments.
        
        Args:
            vad_metrics: Voice activity detection metrics containing RMS
            noise_floor_history: History of RMS values from non-speech
            noise_update_counter: Counter for update interval
            noise_update_interval: How often to update (number of non-speech chunks)
            
        Returns:
            tuple: (noise_floor, noise_floor_history, noise_update_counter)
        """
        noise_floor_history.append(vad_metrics['rms'])
        noise_update_counter += 1
        
        if noise_update_counter >= noise_update_interval:
            if len(noise_floor_history) >= 20:
                # Use median of recent non-speech segments
                new_noise_floor = float(np.median(noise_floor_history[-50:]))
                logger.info(f"🔄 Updated noise floor to {new_noise_floor:.6f}")
                noise_floor_history = noise_floor_history[-100:]  # Keep recent history
                noise_update_counter = 0
                return new_noise_floor, noise_floor_history, noise_update_counter
            noise_update_counter = 0
        
        return self.noise_floor, noise_floor_history, noise_update_counter
    
    def _handle_language_auto_lock(self, result: dict) -> None:
        """
        Handle language auto-lock logic based on detected language.
        
        Args:
            result: Transcription result dictionary containing language detection
        """
        if not self.language_lock_enabled or self.language_locked:
            return
        
        detected_lang = result.get('language')
        if not detected_lang:
            return
        
        # Map language name back to code
        lang_code_map = {
            'Chinese': 'zh',
            'English': 'en',
            'Japanese': 'ja',
            'Korean': 'ko',
            'Cantonese': 'yue'
        }
        lang_code = lang_code_map.get(detected_lang)
        if not lang_code:
            return
        
        self.language_detections.append(lang_code)
        
        # Check if warmup period complete
        warmup_elapsed = time.time() - self.language_warmup_start
        warmup_target = self.config.get('language_lock_warmup_s', 10.0)
        min_samples = self.config.get('language_lock_min_samples', 3)
        
        if warmup_elapsed >= warmup_target and len(self.language_detections) >= min_samples:
            # Calculate language distribution
            from collections import Counter
            lang_counts = Counter(self.language_detections)
            total = len(self.language_detections)
            most_common_lang, count = lang_counts.most_common(1)[0]
            confidence = count / total
            
            lock_threshold = self.config.get('language_lock_confidence', 0.6)
            if confidence >= lock_threshold:
                self.current_language = most_common_lang
                self.language_locked = True
                logger.info(f"🔒 Language LOCKED to '{most_common_lang}' "
                          f"(confidence: {confidence:.1%}, samples: {count}/{total})")
            else:
                logger.info(f"⚠️ Language detection inconclusive after warmup "
                          f"(best: {most_common_lang} at {confidence:.1%}), "
                          f"remaining in auto mode")
                # Don't try to lock again
                self.language_locked = True
    
    def _apply_metadata_filtering(self, result: dict) -> tuple:
        """
        Apply metadata-based filtering (BGM, events, etc.).
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            tuple: (should_filter, filter_reason) - bool and string reason
        """
        # Check if BGM filtering is enabled
        if self.config.get('filter_bgm', False):
            if 'BGM' in result.get('audio_events', []):
                return True, "Background music detected"
        
        # Check for specific event filtering
        filter_events = self.config.get('filter_events', [])
        if filter_events:
            for event in result.get('audio_events', []):
                if event in filter_events:
                    return True, f"Filtered event: {event}"
        
        return False, None
    
    def _build_display_text(self, text: str, result: dict) -> str:
        """
        Build formatted display text with emojis and metadata.
        
        Args:
            text: Base transcription text
            result: Transcription result dictionary with metadata
            
        Returns:
            str: Formatted display text
        """
        display_parts = []
        
        # Add emotion emoji if present and enabled
        if self.config.get('show_emotions', False) and result.get('emotion'):
            from transcription_decoder import EMOTION_TAGS
            emoji = EMOTION_TAGS.get(result['emotion'], '')
            display_parts.append(emoji)
        
        # Add audio event emojis if present and enabled
        if self.config.get('show_events', True) and result.get('audio_events'):
            from transcription_decoder import AUDIO_EVENT_TAGS
            for event in result['audio_events']:
                emoji = AUDIO_EVENT_TAGS.get(event, '')
                display_parts.append(emoji)
        
        # Add the transcription text
        display_parts.append(text)
        
        # Add language tag if detected and enabled
        if self.config.get('show_language', True) and result.get('language'):
            display_parts.append(f"[{result['language']}]")
        
        return ' '.join(display_parts)
    
    def _emit_transcription(self, display_text: str, result: dict, new_words: list = None) -> None:
        """
        Emit transcription to console and WebSocket.
        
        Args:
            display_text: Formatted text to display
            result: Full transcription result dictionary
            new_words: Optional list of new words (for timeline merging)
        """
        print(f"TRANSCRIPT: {display_text}")
        sys.stdout.flush()
        
        # Update result for WebSocket if using timeline merging
        if new_words is not None:
            result['words'] = new_words
        
        # Broadcast via WebSocket
        self.websocket_manager.broadcast_transcription(result)
    
    def _process_audio_worker(self) -> None:
        """
        Main audio processing worker thread.
        
        Orchestrates the complete audio processing pipeline:
        1. Buffer audio chunks from queue
        2. Bootstrap/update noise floor calibration
        3. Resample audio to model rate (16kHz)
        4. Perform voice activity detection (VAD)
        5. Generate audio features for NPU
        6. Run NPU inference
        7. Decode transcription with timestamps
        8. Apply language auto-lock if enabled
        9. Filter based on metadata (BGM, events)
        10. Merge chunks using timeline (if enabled) or text deduplication
        11. Format and emit transcription output
        
        This method runs in a separate daemon thread until is_recording is set to False.
        """
        audio_buffer = np.array([], dtype=np.int16)

        # Size thresholds in device samples
        dev_rate = int(self.device_rate or 16000)
        buffer_size_dev = int(dev_rate * self.chunk_duration)
        overlap_size_dev = int(dev_rate * self.overlap_duration)

        logger.info(f"Audio worker started | Buffer: {self.chunk_duration}s | Overlap: {self.overlap_duration}s | dev={dev_rate}Hz → model=16000Hz")

        # Noise floor calibration
        calib_needed = int(dev_rate * self.noise_calib_secs)
        rms_accum = []
        seen_for_calib = 0
        
        # Adaptive noise floor tracking
        noise_floor_history = []
        noise_update_counter = 0
        noise_update_interval = 50  # Update every 50 non-speech chunks

        while self.is_recording:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                audio_buffer = np.concatenate([audio_buffer, chunk])

                # Bootstrap noise floor from first N seconds
                if self.noise_floor is None and seen_for_calib < calib_needed:
                    self.noise_floor, seen_for_calib = self._bootstrap_noise_floor(
                        audio_buffer, rms_accum, seen_for_calib, calib_needed
                    )
                    continue

                if len(audio_buffer) < buffer_size_dev:
                    continue

                # Resample to model rate
                x16 = self.audio_processor.resample_to_model_rate(audio_buffer)

                # Advanced Voice Activity Detection
                is_speech, vad_metrics = self.audio_processor.is_speech_segment(x16, self.noise_floor)
                
                if not is_speech:
                    logger.debug(f"Skip (VAD): RMS={vad_metrics['rms']:.4f} ZCR={vad_metrics['zcr']:.3f} "
                               f"Entropy={vad_metrics['spectral_entropy']:.3f}")
                    
                    # Update adaptive noise floor from non-speech segments
                    self.noise_floor, noise_floor_history, noise_update_counter = self._update_adaptive_noise_floor(
                        vad_metrics, noise_floor_history, noise_update_counter, noise_update_interval
                    )
                    
                    audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)
                    continue
                
                logger.debug(f"✅ Speech detected: RMS={vad_metrics['rms']:.4f} ZCR={vad_metrics['zcr']:.3f} "
                           f"Entropy={vad_metrics['spectral_entropy']:.3f}")

                # Generate audio fingerprint to detect duplicate chunks from overlap
                import hashlib
                audio_hash = hashlib.md5(x16.tobytes()).hexdigest()[:16]
                
                # Start language warmup timer on first speech
                if self.language_lock_enabled and not self.language_locked and self.language_warmup_start is None:
                    self.language_warmup_start = time.time()
                    logger.info("🌍 Language detection warmup started")
                
                # Convert to features (use current_language which may be auto or locked)
                mel_input = self.audio_processor.audio_to_features(
                    x16, self.current_language, self.config['use_itn']
                )

                if mel_input is not None:
                    # Run inference
                    start_time = time.time()
                    npu_output = self.model_manager.run_inference(mel_input)
                    inference_time = (time.time() - start_time) * 1000

                    if npu_output is not None:
                        # Record statistics
                        self.statistics.record_inference(inference_time)

                        # Decode transcription with audio hash for deduplication
                        # Returns dict with text, language, emotion, audio_events
                        result = self.transcription_decoder.decode_output(npu_output, audio_hash)

                        if result is not None:
                            # Store audio hash with result for chunk deduplication
                            self.transcription_decoder.add_audio_hash(audio_hash, result)
                            
                            # Language auto-lock logic
                            self._handle_language_auto_lock(result)
                            
                            # Apply metadata-based filtering
                            should_filter, filter_reason = self._apply_metadata_filtering(result)
                            
                            if should_filter:
                                logger.debug(f"🚫 {filter_reason}: '{result['text']}'")
                                audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)
                                self.chunk_counter += 1
                                continue
                            
                            # Use timeline-based merging if enabled
                            if self.enable_timeline_merging and result.get('words'):
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
                                    display_text = self._build_display_text(new_text, result)
                                    
                                    # Update result with new text
                                    result['text'] = new_text
                                    
                                    # Emit transcription
                                    self._emit_transcription(display_text, result, new_words)
                            else:
                                # Fallback to legacy text-based display
                                display_text = self._build_display_text(result['text'], result)
                                self._emit_transcription(display_text, result)
                            
                            # Increment chunk counter for timeline tracking
                            self.chunk_counter += 1

                # Keep overlap in device samples
                audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Audio processing error: {e}")
                self.statistics.record_error()

    def _find_audio_device(self, device_name: str = None) -> int:
        """Find audio device by name"""
        audio = pyaudio.PyAudio()

        try:
            device_count = audio.get_device_count()
            logger.info(f"Scanning {device_count} audio devices...")

            target_device = None
            devices_found = []

            for i in range(device_count):
                try:
                    device_info = audio.get_device_info_by_index(i)
                    device_name_clean = device_info['name'].strip()
                    devices_found.append(f"Device {i}: {device_name_clean}")

                    if device_info['maxInputChannels'] > 0:
                        if 'AIRHUG' in device_name_clean.upper():
                            target_device = i
                            logger.info(f"Found AIRHUG device: {device_name_clean} (Device {i})")
                            break

                except Exception as e:
                    logger.debug(f"Error checking device {i}: {e}")
                    continue

            logger.info("Available audio devices:")
            for device in devices_found:
                logger.info(f"  {device}")

            if target_device is None:
                default_device = audio.get_default_input_device_info()
                target_device = default_device['index']
                logger.info(f"AIRHUG not found, using default: {default_device['name']} (Device {target_device})")

            return target_device

        finally:
            audio.terminate()

    def _get_device_sample_rate(self, device_index: int) -> int:
        """Auto-detect supported sample rate for device"""
        audio = pyaudio.PyAudio()

        try:
            device_info = audio.get_device_info_by_index(device_index)
            logger.info(f"Device info: {device_info['name']}")
            logger.info(f"   Default sample rate: {device_info['defaultSampleRate']}")

            test_rates = [16000, 44100, 48000, 22050, 8000]

            for rate in test_rates:
                try:
                    audio.is_format_supported(
                        rate, input_device=device_index,
                        input_channels=1, input_format=pyaudio.paInt16
                    )
                    logger.info(f"Sample rate {rate}Hz supported")
                    return rate
                except ValueError:
                    logger.debug(f"Sample rate {rate}Hz not supported")
                    continue

            default_rate = int(device_info['defaultSampleRate'])
            logger.warning(f"Using device default sample rate: {default_rate}Hz")
            return default_rate

        finally:
            audio.terminate()

    def start_transcription(self) -> None:
        """Start live transcription"""
        try:
            # Start WebSocket server
            if not self.websocket_manager.start_server():
                logger.warning("WebSocket server failed to start - continuing without WebSocket support")

            # Find audio device
            device_index = self._find_audio_device(self.config.get('audio_device'))
            if device_index is None:
                raise RuntimeError("No suitable audio device found")

            # Auto-detect sample rate
            detected_sample_rate = self._get_device_sample_rate(device_index)
            self.device_rate = int(detected_sample_rate)
            self.audio_processor.set_device_rate(self.device_rate)

            # Pick supported params
            self.device_rate, self.channels = self._pick_stream_params(device_index)

            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()

            # Open audio stream
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.device_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )

            logger.info(f"Audio stream opened: {self.device_rate} Hz, {self.channels} ch (Device {device_index})")

            # Start recording
            self.is_recording = True
            self.stream.start_stream()

            # Calibrate noise floor
            self._calibrate_noise_floor(timeout_s=self.noise_calib_secs)

            # Start processing worker
            self.worker_thread = threading.Thread(target=self._process_audio_worker, daemon=True)
            self.worker_thread.start()

            logger.info("Live transcription started! Speak into the microphone...")
            logger.info("Press Ctrl+C to stop")

            # Keep running until interrupted
            try:
                while self.is_recording:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise
        finally:
            self.stop_transcription()

    def stop_transcription(self) -> None:
        """Stop live transcription"""
        logger.info("Stopping transcription...")

        self.is_recording = False

        # Stop audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio:
            self.audio.terminate()

        # Stop worker thread
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)

        # Stop WebSocket server
        self.websocket_manager.stop_server()

        # Print final statistics
        self.statistics.print_summary()

        # Cleanup model
        self.model_manager.cleanup()

        logger.info("Transcription stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main application entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create and start transcriber
        transcriber = LiveTranscriber()
        transcriber.start_transcription()

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
