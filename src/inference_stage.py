"""
Inference Stage
===============
Stage 2 of the pipeline: NPU inference.

Responsibilities:
- Run RKNN model inference on NPU
- Track inference timing
- Pass results to next stage

This stage is NPU-bound and is the bottleneck. By running it in parallel
with preprocessing and postprocessing, we maximize throughput.
"""

import logging
import time
from typing import Any, Optional, Dict
from pipeline_stage import PipelineStage

logger = logging.getLogger(__name__)


class InferenceStage(PipelineStage):
    """
    Inference stage: NPU model execution.
    
    Input: {
        'mel_features': np.ndarray,
        'audio_hash': str,
        'vad_metrics': dict,
        'language': str,
        'use_itn': bool,
        'chunk_counter': int
    }
    
    Output: {
        'npu_output': np.ndarray,
        'audio_hash': str,
        'language': str,
        'use_itn': bool,
        'chunk_counter': int,
        'inference_time_ms': float
    }
    """

    def __init__(self, input_queue, output_queue, model_manager, statistics_tracker):
        """
        Initialize inference stage.
        
        Args:
            input_queue: Queue receiving preprocessed features
            output_queue: Queue sending inference results
            model_manager: ModelManager instance
            statistics_tracker: StatisticsTracker instance
        """
        super().__init__("Inference", input_queue, output_queue)
        
        self.model_manager = model_manager
        self.statistics = statistics_tracker
        
        logger.info("InferenceStage initialized")

    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Run NPU inference on preprocessed features.
        
        Args:
            item: Preprocessed features from previous stage
            
        Returns:
            Inference results dict or None if inference failed
        """
        try:
            mel_features = item['mel_features']
            audio_hash = item['audio_hash']
            
            # Run NPU inference (this is the bottleneck, ~50-100ms)
            start_time = time.time()
            npu_output = self.model_manager.run_inference(mel_features)
            inference_time_ms = (time.time() - start_time) * 1000
            
            if npu_output is None:
                logger.warning(f"NPU inference returned None for hash {audio_hash}")
                return None
            
            # Record statistics
            self.statistics.record_inference(inference_time_ms)
            
            logger.debug(f"🚀 NPU Inference: {inference_time_ms:.1f}ms | Hash: {audio_hash}")
            
            # Pass results to next stage
            return {
                'npu_output': npu_output,
                'audio_hash': audio_hash,
                'language': item['language'],
                'use_itn': item['use_itn'],
                'chunk_counter': item['chunk_counter'],
                'inference_time_ms': inference_time_ms,
                'vad_metrics': item.get('vad_metrics', {})
            }
            
        except Exception as e:
            logger.error(f"Inference error: {e}", exc_info=True)
            return None
