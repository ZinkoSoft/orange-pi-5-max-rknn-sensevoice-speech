"""
Pipeline Orchestrator
=====================
Coordinates all pipeline stages and manages data flow between them.

Architecture:
    Audio Buffer
        ↓
    [Stage 1: Preprocessing] → Queue 1
        ↓
    [Stage 2: Inference] → Queue 2
        ↓
    [Stage 3: Postprocessing] → AsyncEmitter
        ↓
    WebSocket + Console

Each stage runs in its own thread, processing in parallel:
- While Stage 2 does NPU inference on chunk N
- Stage 1 preprocesses chunk N+1
- Stage 3 post-processes chunk N-1

Following SOLID principles:
- Single Responsibility: Only coordinates stages
- Open/Closed: Easy to add new stages
- Dependency Injection: All components passed in
"""

import logging
import queue
from typing import Dict, Any, List
from preprocessing_stage import PreprocessingStage
from inference_stage import InferenceStage
from postprocessing_stage import PostprocessingStage
from async_emitter import AsyncEmitter

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates parallel processing pipeline with multiple stages.
    
    Manages:
    - Stage lifecycle (start/stop)
    - Inter-stage queues
    - Statistics collection
    - Error handling
    """

    def __init__(self, config: Dict[str, Any], audio_processor, noise_calibrator,
                 model_manager, transcription_decoder, language_manager,
                 transcription_formatter, timeline_merger, statistics_tracker,
                 text_post_processor, websocket_manager):
        """
        Initialize pipeline orchestrator.
        
        Args:
            config: Configuration dictionary
            audio_processor: AudioProcessor instance
            noise_calibrator: NoiseFloorCalibrator instance
            model_manager: ModelManager instance
            transcription_decoder: TranscriptionDecoder instance
            language_manager: LanguageLockManager instance
            transcription_formatter: TranscriptionFormatter instance
            timeline_merger: TimelineMerger instance (or None)
            statistics_tracker: StatisticsTracker instance
            text_post_processor: TextPostProcessor instance
            websocket_manager: WebSocketManager instance
        """
        self.config = config
        self.is_running = False
        
        # Queue sizes from config (with defaults)
        preprocess_queue_size = config.get('pipeline_preprocess_queue_size', 3)
        inference_queue_size = config.get('pipeline_inference_queue_size', 2)
        postprocess_queue_size = config.get('pipeline_postprocess_queue_size', 2)
        emit_queue_size = config.get('pipeline_emit_queue_size', 10)
        
        # Create inter-stage queues
        self.preprocess_queue = queue.Queue(maxsize=preprocess_queue_size)
        self.inference_queue = queue.Queue(maxsize=inference_queue_size)
        self.postprocess_queue = queue.Queue(maxsize=postprocess_queue_size)
        
        # Create async emitter
        self.async_emitter = AsyncEmitter(
            transcription_formatter,
            websocket_manager,
            queue_size=emit_queue_size
        )
        
        # Create pipeline stages
        self.preprocessing_stage = PreprocessingStage(
            self.preprocess_queue,
            self.inference_queue,
            audio_processor,
            noise_calibrator,
            language_manager,
            config
        )
        
        self.inference_stage = InferenceStage(
            self.inference_queue,
            self.postprocess_queue,
            model_manager,
            statistics_tracker
        )
        
        self.postprocessing_stage = PostprocessingStage(
            self.postprocess_queue,
            transcription_decoder,
            language_manager,
            timeline_merger,
            transcription_formatter,
            text_post_processor,
            self.async_emitter,
            config
        )
        
        # Stage list for easy management
        self.stages = [
            self.preprocessing_stage,
            self.inference_stage,
            self.postprocessing_stage
        ]
        
        logger.info("PipelineOrchestrator initialized with 3 stages + async emitter")

    def start(self) -> bool:
        """
        Start all pipeline stages.
        
        Returns:
            bool: True if all stages started successfully
        """
        if self.is_running:
            logger.warning("Pipeline already running")
            return False
        
        logger.info("Starting parallel processing pipeline...")
        
        # Start async emitter first
        if not self.async_emitter.start():
            logger.error("Failed to start async emitter")
            return False
        
        # Start all stages
        for stage in self.stages:
            if not stage.start():
                logger.error(f"Failed to start stage: {stage.name}")
                self.stop()  # Clean up already started stages
                return False
        
        self.is_running = True
        logger.info("✅ Parallel processing pipeline started (3 stages + async emitter)")
        logger.info("    Stage 1: Preprocessing (Resample + VAD + Features)")
        logger.info("    Stage 2: NPU Inference")
        logger.info("    Stage 3: Postprocessing (Decode + Merge + Emit)")
        return True

    def stop(self) -> None:
        """Stop all pipeline stages gracefully"""
        if not self.is_running:
            return
        
        logger.info("Stopping parallel processing pipeline...")
        
        # Stop stages in reverse order
        for stage in reversed(self.stages):
            stage.stop()
        
        # Stop async emitter last
        self.async_emitter.stop()
        
        self.is_running = False
        logger.info("Parallel processing pipeline stopped")
        
        # Print statistics
        self._print_statistics()

    def submit_audio_chunk(self, audio_buffer, chunk_counter: int) -> bool:
        """
        Submit audio buffer to preprocessing stage.
        
        Args:
            audio_buffer: Raw audio buffer (device sample rate)
            chunk_counter: Current chunk number
            
        Returns:
            bool: True if queued, False if queue full
        """
        if not self.is_running:
            logger.warning("Pipeline not running, cannot submit audio chunk")
            return False
        
        try:
            # Non-blocking put to prevent audio callback blocking
            self.preprocess_queue.put_nowait({
                'audio_buffer': audio_buffer,
                'chunk_counter': chunk_counter
            })
            return True
        except queue.Full:
            logger.warning("⚠️ Preprocessing queue full, dropping audio chunk")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from all stages.
        
        Returns:
            dict: Comprehensive statistics
        """
        stats = {
            'pipeline_running': self.is_running,
            'stages': {},
            'queues': {},
            'emitter': {}
        }
        
        # Stage statistics
        for stage in self.stages:
            stats['stages'][stage.name] = stage.get_stats()
        
        # Queue sizes
        stats['queues'] = {
            'preprocess': self.preprocess_queue.qsize(),
            'inference': self.inference_queue.qsize(),
            'postprocess': self.postprocess_queue.qsize(),
            'emit': self.async_emitter.get_queue_size()
        }
        
        # Emitter statistics
        stats['emitter'] = self.async_emitter.get_stats()
        
        return stats

    def _print_statistics(self) -> None:
        """Print comprehensive pipeline statistics"""
        stats = self.get_statistics()
        
        logger.info("=" * 60)
        logger.info("PIPELINE STATISTICS")
        logger.info("=" * 60)
        
        # Stage statistics
        for stage_name, stage_stats in stats['stages'].items():
            logger.info(f"\n{stage_name} Stage:")
            logger.info(f"  Processed: {stage_stats['processed']}")
            logger.info(f"  Skipped: {stage_stats['skipped']}")
            logger.info(f"  Errors: {stage_stats['errors']}")
            logger.info(f"  Avg Time: {stage_stats['avg_time_ms']:.1f}ms")
        
        # Emitter statistics
        emitter_stats = stats['emitter']
        logger.info(f"\nAsync Emitter:")
        logger.info(f"  Emitted: {emitter_stats['emitted']}")
        logger.info(f"  Dropped: {emitter_stats['dropped']}")
        logger.info(f"  Errors: {emitter_stats['errors']}")
        
        logger.info("=" * 60)

    def get_queue_depths(self) -> Dict[str, int]:
        """
        Get current queue depths for monitoring.
        
        Returns:
            dict: Queue depths
        """
        return {
            'preprocess': self.preprocess_queue.qsize(),
            'inference': self.inference_queue.qsize(),
            'postprocess': self.postprocess_queue.qsize(),
            'emit': self.async_emitter.get_queue_size()
        }
