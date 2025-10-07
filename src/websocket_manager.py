#!/usr/bin/env python3
"""
WebSocket Management Module
===========================
Handles WebSocket server setup and real-time transcription broadcasting.
"""

import asyncio
import threading
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket server for real-time transcription streaming"""

    def __init__(self, config: dict):
        self.config = config
        self.websocket_server = None
        self.websocket_thread = None
        self.websocket_loop = None
        self.is_running = False

    def initialize(self) -> bool:
        """Initialize WebSocket server"""
        try:
            from websocket_server import get_websocket_server
            self.websocket_server = get_websocket_server()
            self.websocket_server.host = self.config.get('websocket_host', '0.0.0.0')
            self.websocket_server.port = self.config.get('websocket_port', 8765)
            logger.info(f"📡 WebSocket server configured on {self.websocket_server.host}:{self.websocket_server.port}")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket server initialization failed: {e}")
            return False

    def start_server(self) -> bool:
        """Start WebSocket server in a separate thread"""
        if not self.websocket_server:
            logger.error("❌ WebSocket server not initialized")
            return False

        try:
            # Start WebSocket server in background thread
            def websocket_worker():
                self.websocket_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.websocket_loop)

                try:
                    # Start the WebSocket server
                    self.websocket_loop.run_until_complete(
                        self.websocket_server.start_server()
                    )
                    # Keep the loop running
                    self.websocket_loop.run_forever()
                except Exception as e:
                    logger.error(f"❌ WebSocket server error: {e}")
                finally:
                    self.websocket_loop.close()

            self.websocket_thread = threading.Thread(target=websocket_worker, daemon=True)
            self.websocket_thread.start()

            # Give server time to start
            import time
            time.sleep(1.0)
            self.is_running = True
            logger.info(f"✅ WebSocket server started on ws://{self.websocket_server.host}:{self.websocket_server.port}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            return False

    def broadcast_transcription(self, result: dict) -> None:
        """
        Broadcast rich transcription with metadata to all connected WebSocket clients.
        
        Args:
            result: dict with keys: text, language, emotion, audio_events, raw_text
        """
        if not self.is_running or not self.websocket_loop:
            return

        try:
            from websocket_server import broadcast_transcription
            
            # If result is a string (legacy), convert to dict
            if isinstance(result, str):
                result = {'text': result, 'language': None, 'emotion': None, 'audio_events': []}
            
            asyncio.run_coroutine_threadsafe(
                broadcast_transcription(result),
                self.websocket_loop
            )
        except Exception as e:
            logger.debug(f"⚠️ WebSocket broadcast error: {e}")

    def broadcast_status(self, status: dict) -> None:
        """Broadcast status update to all connected WebSocket clients"""
        if not self.is_running or not self.websocket_loop:
            return

        try:
            from websocket_server import broadcast_status
            asyncio.run_coroutine_threadsafe(
                broadcast_status(status),
                self.websocket_loop
            )
        except Exception as e:
            logger.debug(f"⚠️ WebSocket status broadcast error: {e}")

    def stop_server(self) -> None:
        """Stop WebSocket server"""
        logger.info("🛑 Stopping WebSocket server...")

        if self.websocket_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.websocket_server.stop_server(),
                    self.websocket_loop
                ).result(timeout=5.0)
                self.websocket_loop.call_soon_threadsafe(self.websocket_loop.stop)
            except Exception as e:
                logger.debug(f"WebSocket cleanup error: {e}")

        if self.websocket_thread:
            self.websocket_thread.join(timeout=5.0)

        self.is_running = False
        logger.info("✅ WebSocket server stopped")

    def is_server_running(self) -> bool:
        """Check if WebSocket server is running"""
        return self.is_running