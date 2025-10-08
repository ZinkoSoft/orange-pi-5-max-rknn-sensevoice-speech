"""
Async Emitter
==============
Non-blocking emission of transcription results to WebSocket and console.
Prevents I/O operations from blocking the main processing pipeline.

Following SOLID principles:
- Single Responsibility: Only handles output emission
- Open/Closed: Easy to extend with new output targets
- Dependency Injection: Takes formatter and websocket manager
"""

import logging
import queue
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AsyncEmitter:
    """
    Non-blocking emitter for transcription results.
    
    Runs emission (WebSocket, console, file) in a separate thread
    to prevent I/O blocking from affecting the processing pipeline.
    """

    def __init__(self, formatter, websocket_manager, queue_size: int = 10):
        """
        Initialize async emitter.
        
        Args:
            formatter: TranscriptionFormatter instance
            websocket_manager: WebSocketManager instance
            queue_size: Maximum queue size (prevents memory overflow)
        """
        self.formatter = formatter
        self.websocket_manager = websocket_manager
        self.emit_queue = queue.Queue(maxsize=queue_size)
        self.is_running = False
        self.emit_thread = None
        self.stats = {
            'emitted': 0,
            'dropped': 0,
            'errors': 0
        }
        
        logger.info("AsyncEmitter initialized")

    def start(self) -> bool:
        """
        Start the emission thread.
        
        Returns:
            bool: True if successful
        """
        if self.is_running:
            logger.warning("AsyncEmitter already running")
            return False
        
        self.is_running = True
        self.emit_thread = threading.Thread(
            target=self._emit_worker,
            name="AsyncEmitter",
            daemon=True
        )
        self.emit_thread.start()
        
        logger.info("✅ AsyncEmitter started")
        return True

    def stop(self) -> None:
        """Stop the emission thread gracefully"""
        if not self.is_running:
            return
        
        logger.info("Stopping AsyncEmitter...")
        self.is_running = False
        
        # Signal stop by putting None
        try:
            self.emit_queue.put(None, timeout=1.0)
        except queue.Full:
            pass
        
        if self.emit_thread:
            self.emit_thread.join(timeout=2.0)
        
        logger.info(f"AsyncEmitter stopped | Emitted: {self.stats['emitted']} | "
                   f"Dropped: {self.stats['dropped']} | Errors: {self.stats['errors']}")

    def emit(self, text: str, result: Dict[str, Any], words: Optional[List[Dict]] = None) -> bool:
        """
        Queue transcription for emission (non-blocking).
        
        Args:
            text: Transcription text
            result: Full result dictionary with metadata
            words: Optional list of word dictionaries with timestamps
            
        Returns:
            bool: True if queued, False if dropped (queue full)
        """
        try:
            # Non-blocking put
            self.emit_queue.put_nowait({
                'text': text,
                'result': result,
                'words': words
            })
            return True
        except queue.Full:
            self.stats['dropped'] += 1
            logger.warning(f"⚠️ Emission queue full, dropped result (total dropped: {self.stats['dropped']})")
            return False

    def _emit_worker(self) -> None:
        """
        Worker thread that performs actual emission.
        
        Runs in background, pulling from queue and emitting results.
        All I/O blocking happens here, not in the main pipeline.
        """
        logger.info("AsyncEmitter worker thread started")
        
        while self.is_running:
            try:
                # Wait for next emission
                item = self.emit_queue.get(timeout=0.5)
                
                # None is stop signal
                if item is None:
                    break
                
                # Perform emission (all blocking I/O happens here)
                self._do_emit(item)
                
                self.stats['emitted'] += 1
                
            except queue.Empty:
                continue
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"❌ Emission error: {e}", exc_info=True)
        
        logger.info("AsyncEmitter worker thread stopped")

    def _do_emit(self, item: Dict[str, Any]) -> None:
        """
        Perform actual emission to all outputs.
        
        Args:
            item: Dictionary with 'text', 'result', 'words'
        """
        try:
            text = item['text']
            result = item['result']
            words = item.get('words')
            
            # Format display text
            display_text = self.formatter.format_display_text(text, result)
            
            # Emit to console (blocking, but in background thread)
            print(display_text, flush=True)
            
            # Emit to WebSocket (blocking, but in background thread)
            if self.websocket_manager and self.websocket_manager.is_running:
                try:
                    # Use the correct broadcast method
                    if isinstance(result, dict):
                        self.websocket_manager.broadcast_transcription(result)
                    else:
                        # Fallback for string results
                        self.websocket_manager.broadcast_transcription({'text': text})
                except Exception as e:
                    logger.debug(f"WebSocket broadcast error: {e}")
            
            # Could add more outputs here: file, database, HTTP API, etc.
            # All blocking I/O is isolated in this background thread
            
        except Exception as e:
            logger.error(f"Error in _do_emit: {e}")
            raise

    def get_stats(self) -> Dict[str, int]:
        """
        Get emission statistics.
        
        Returns:
            dict: Statistics dictionary
        """
        return self.stats.copy()

    def get_queue_size(self) -> int:
        """
        Get current queue size.
        
        Returns:
            int: Number of items in queue
        """
        return self.emit_queue.qsize()
