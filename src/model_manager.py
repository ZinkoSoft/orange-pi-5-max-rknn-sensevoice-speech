#!/usr/bin/env python3
"""
Model Management Module
=======================
Handles RKNN model loading, initialization, and inference operations.
"""

import time
import numpy as np
from typing import Optional, Dict, Any
import logging
from rknnlite.api import RKNNLite

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages RKNN model operations"""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.rknn = None
        self.is_initialized = False

    def initialize(self) -> bool:
        """Initialize and load the RKNN model"""
        try:
            logger.info(f"📥 Loading RKNN model: {self.model_path}")

            self.rknn = RKNNLite()

            # Load model
            ret = self.rknn.load_rknn(self.model_path)
            if ret != 0:
                raise RuntimeError(f"Failed to load RKNN model: {ret}")

            # Initialize runtime - use single core for sequential inference
            # Using all 3 cores adds overhead without benefit for single-threaded processing
            ret = self.rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0)
            if ret != 0:
                raise RuntimeError(f"Failed to initialize RKNN runtime: {ret}")

            self.is_initialized = True
            logger.info("✅ NPU model loaded and initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Model initialization failed: {e}")
            self.is_initialized = False
            return False

    def run_inference(self, inputs: np.ndarray) -> Optional[np.ndarray]:
        """Run inference on the model"""
        if not self.is_initialized:
            logger.error("❌ Model not initialized")
            return None

        try:
            start_time = time.time()

            # Run NPU inference
            outputs = self.rknn.inference(inputs=[inputs])

            inference_time = (time.time() - start_time) * 1000

            if outputs is None or len(outputs) == 0:
                logger.error("❌ NPU inference returned no outputs")
                return None

            logger.debug(f"🚀 NPU Inference: {inference_time:.1f}ms | Output: {outputs[0].shape}")

            return outputs[0]

        except Exception as e:
            logger.error(f"❌ NPU inference error: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up model resources"""
        if self.rknn:
            try:
                self.rknn.release()
                logger.info("✅ Model resources released")
            except Exception as e:
                logger.warning(f"⚠️ Error releasing model resources: {e}")
            finally:
                self.rknn = None
                self.is_initialized = False