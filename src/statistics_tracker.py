#!/usr/bin/env python3
"""
Statistics Tracking Module
==========================
Handles performance metrics and statistics collection.
"""

import time
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class StatisticsTracker:
    """Tracks performance statistics and metrics"""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Reset all statistics"""
        self.stats = {
            'total_chunks_processed': 0,
            'total_inference_time': 0.0,
            'average_inference_time': 0.0,
            'errors': 0,
            'start_time': time.time()
        }

    def record_inference(self, inference_time_ms: float) -> None:
        """Record an inference operation"""
        self.stats['total_chunks_processed'] += 1
        self.stats['total_inference_time'] += inference_time_ms
        self.stats['average_inference_time'] = (
            self.stats['total_inference_time'] / self.stats['total_chunks_processed']
        )

    def record_error(self) -> None:
        """Record an error"""
        self.stats['errors'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        current_time = time.time()
        total_time = current_time - self.stats['start_time']

        return {
            **self.stats,
            'total_runtime_seconds': total_time,
            'chunks_per_second': self.stats['total_chunks_processed'] / total_time if total_time > 0 else 0,
            'error_rate': self.stats['errors'] / self.stats['total_chunks_processed'] if self.stats['total_chunks_processed'] > 0 else 0
        }

    def print_summary(self) -> None:
        """Print statistics summary"""
        stats = self.get_stats()
        logger.info("📊 Session Statistics:")
        logger.info(f"   Total runtime: {stats['total_runtime_seconds']:.1f}s")
        logger.info(f"   Chunks processed: {stats['total_chunks_processed']}")
        logger.info(f"   Chunks per second: {stats['chunks_per_second']:.2f}")
        logger.info(f"   Average inference: {stats['average_inference_time']:.1f}ms")
        logger.info(f"   Errors: {stats['errors']} ({stats['error_rate']:.1%})")