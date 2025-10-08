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
import signal

# Import modular components
from config import ConfigManager
from model_manager import ModelManager
from audio_processor import AudioProcessor
from transcription_decoder import TranscriptionDecoder
from websocket_manager import WebSocketManager
from statistics_tracker import StatisticsTracker
from timeline_merger import TimelineMerger

# Import new specialized components
from audio_stream_manager import AudioStreamManager
from noise_floor_calibrator import NoiseFloorCalibrator
from language_lock_manager import LanguageLockManager
from transcription_formatter import TranscriptionFormatter
from audio_processing_pipeline import AudioProcessingPipeline

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

        # Initialize core components
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

        # Initialize specialized components
        self.audio_stream = AudioStreamManager(self.config)
        self.noise_calibrator = NoiseFloorCalibrator(self.config)
        self.language_manager = LanguageLockManager(self.config)
        self.formatter = TranscriptionFormatter(self.config, self.websocket_manager)
        
        # Initialize audio processing pipeline
        self.pipeline = AudioProcessingPipeline(
            self.config,
            self.audio_stream,
            self.noise_calibrator,
            self.audio_processor,
            self.model_manager,
            self.transcription_decoder,
            self.language_manager,
            self.formatter,
            self.timeline_merger,
            self.statistics
        )
        
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

    def start_transcription(self) -> None:
        """Start live transcription"""
        try:
            # Start WebSocket server
            if not self.websocket_manager.start_server():
                logger.warning("WebSocket server failed to start - continuing without WebSocket support")

            # Initialize audio stream
            if not self.audio_stream.initialize_stream():
                raise RuntimeError("Failed to initialize audio stream")

            # Set device rate in audio processor
            stream_info = self.audio_stream.get_stream_info()
            self.audio_processor.set_device_rate(stream_info['device_rate'])

            # Start recording
            if not self.audio_stream.start_recording():
                raise RuntimeError("Failed to start audio recording")

            # Start audio processing pipeline
            if not self.pipeline.start():
                raise RuntimeError("Failed to start audio processing pipeline")

            logger.info("Live transcription started! Speak into the microphone...")
            logger.info("Press Ctrl+C to stop")

            # Keep running until interrupted
            try:
                while self.audio_stream.is_recording:
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

        # Stop audio processing pipeline
        self.pipeline.stop()

        # Stop audio recording
        self.audio_stream.stop_recording()

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
