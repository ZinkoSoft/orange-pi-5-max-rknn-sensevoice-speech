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

        logger.info("Initializing Live Transcriber with modular components")

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

    def _process_audio_worker(self) -> None:
        """Main audio processing worker"""
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
                    sample = audio_buffer[:min(len(audio_buffer), calib_needed)]
                    rms_accum.append(self.audio_processor.calculate_rms(sample))
                    seen_for_calib = len(sample)
                    if seen_for_calib >= calib_needed:
                        self.noise_floor = float(np.median(rms_accum))
                        logger.info(f"Calibrated noise floor = {self.noise_floor:.6f} (over {self.noise_calib_secs:.1f}s)")
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
                    noise_floor_history.append(vad_metrics['rms'])
                    noise_update_counter += 1
                    
                    if noise_update_counter >= noise_update_interval:
                        if len(noise_floor_history) >= 20:
                            # Use median of recent non-speech segments
                            self.noise_floor = float(np.median(noise_floor_history[-50:]))
                            logger.info(f"🔄 Updated noise floor to {self.noise_floor:.6f}")
                            noise_floor_history = noise_floor_history[-100:]  # Keep recent history
                        noise_update_counter = 0
                    
                    audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)
                    continue
                
                logger.debug(f"✅ Speech detected: RMS={vad_metrics['rms']:.4f} ZCR={vad_metrics['zcr']:.3f} "
                           f"Entropy={vad_metrics['spectral_entropy']:.3f}")

                # Generate audio fingerprint to detect duplicate chunks from overlap
                import hashlib
                audio_hash = hashlib.md5(x16.tobytes()).hexdigest()[:16]
                
                # Convert to features
                mel_input = self.audio_processor.audio_to_features(
                    x16, self.config['language'], self.config['use_itn']
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
                        transcription = self.transcription_decoder.decode_output(npu_output, audio_hash)

                        if transcription is not None:
                            # Store audio hash with transcription for chunk deduplication
                            self.transcription_decoder.add_audio_hash(audio_hash, transcription)
                            
                            print(f"TRANSCRIPT: {transcription}")
                            sys.stdout.flush()

                            # Broadcast via WebSocket
                            self.websocket_manager.broadcast_transcription(transcription)

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
