"""
Pipeline Stage Base Class
==========================
Abstract base class for all pipeline stages.

Following SOLID principles:
- Single Responsibility: Each stage does one thing
- Open/Closed: Easy to add new stages without modifying existing code
- Liskov Substitution: All stages implement same interface
- Interface Segregation: Minimal required interface
- Dependency Injection: Dependencies passed in constructor
"""

import logging
import queue
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.
    
    Each stage:
    - Receives input from an input queue
    - Processes the input
    - Sends output to an output queue
    - Runs in its own thread
    """

    def __init__(self, name: str, input_queue: queue.Queue, 
                 output_queue: Optional[queue.Queue] = None):
        """
        Initialize pipeline stage.
        
        Args:
            name: Stage name for logging
            input_queue: Queue to receive input from
            output_queue: Queue to send output to (optional for final stage)
        """
        self.name = name
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.is_running = False
        self.worker_thread = None
        
        # Statistics
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total_time_ms': 0.0
        }
        
        logger.info(f"Pipeline stage '{name}' initialized")

    def start(self) -> bool:
        """
        Start the stage worker thread.
        
        Returns:
            bool: True if successful
        """
        if self.is_running:
            logger.warning(f"Stage '{self.name}' already running")
            return False
        
        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"Stage-{self.name}",
            daemon=True
        )
        self.worker_thread.start()
        
        logger.info(f"✅ Stage '{self.name}' started")
        return True

    def stop(self) -> None:
        """Stop the stage worker thread gracefully"""
        if not self.is_running:
            return
        
        logger.info(f"Stopping stage '{self.name}'...")
        self.is_running = False
        
        # Signal stop by putting None
        try:
            self.input_queue.put(None, timeout=1.0)
        except queue.Full:
            pass
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        
        logger.info(f"Stage '{self.name}' stopped | "
                   f"Processed: {self.stats['processed']} | "
                   f"Skipped: {self.stats['skipped']} | "
                   f"Errors: {self.stats['errors']} | "
                   f"Avg time: {self._avg_time():.1f}ms")

    def _worker_loop(self) -> None:
        """
        Main worker loop that processes items from input queue.
        
        Runs in separate thread. Calls process() for each item.
        """
        logger.info(f"Stage '{self.name}' worker thread started")
        
        while self.is_running:
            try:
                # Get next item (blocking with timeout)
                item = self.input_queue.get(timeout=0.5)
                
                # None is stop signal
                if item is None:
                    break
                
                # Process the item
                import time
                start_time = time.time()
                
                result = self.process(item)
                
                elapsed_ms = (time.time() - start_time) * 1000
                self.stats['total_time_ms'] += elapsed_ms
                
                # Pass to next stage if we have output
                if result is not None:
                    self.stats['processed'] += 1
                    
                    if self.output_queue:
                        try:
                            self.output_queue.put(result, timeout=1.0)
                        except queue.Full:
                            logger.warning(f"⚠️ Stage '{self.name}' output queue full, dropping result")
                else:
                    self.stats['skipped'] += 1
                
                # Log slow processing
                if elapsed_ms > 100:
                    logger.warning(f"⚠️ Stage '{self.name}' slow processing: {elapsed_ms:.1f}ms")
                
            except queue.Empty:
                continue
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"❌ Error in stage '{self.name}': {e}", exc_info=True)
        
        logger.info(f"Stage '{self.name}' worker thread stopped")

    @abstractmethod
    def process(self, item: Any) -> Optional[Any]:
        """
        Process a single item.
        
        This method must be implemented by each stage.
        
        Args:
            item: Input item from previous stage
            
        Returns:
            Processed result to pass to next stage, or None to skip
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Get stage statistics.
        
        Returns:
            dict: Statistics dictionary
        """
        stats = self.stats.copy()
        stats['avg_time_ms'] = self._avg_time()
        stats['queue_size'] = self.input_queue.qsize()
        return stats

    def _avg_time(self) -> float:
        """Calculate average processing time in ms"""
        if self.stats['processed'] > 0:
            return self.stats['total_time_ms'] / self.stats['processed']
        return 0.0

    def get_queue_size(self) -> int:
        """
        Get current input queue size.
        
        Returns:
            int: Number of items waiting
        """
        return self.input_queue.qsize()
