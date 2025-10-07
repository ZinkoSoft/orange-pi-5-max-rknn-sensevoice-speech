#!/usr/bin/env python3
"""
WebSocket server for streaming live transcriptions
"""

import asyncio
import websockets
import json
import logging
from typing import Set
from datetime import datetime
import functools

logger = logging.getLogger(__name__)

class TranscriptionWebSocketServer:
    """WebSocket server for streaming transcriptions to connected clients"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        
    async def register_client(self, websocket):
        """Register a new WebSocket client"""
        self.clients.add(websocket)
        logger.info(f"🔗 New client connected. Total clients: {len(self.clients)}")
        
        # Send welcome message
        welcome_msg = {
            "type": "status",
            "message": "Connected to NPU SenseVoice Live Transcription",
            "timestamp": datetime.now().isoformat(),
            "clients_connected": len(self.clients)
        }
        await websocket.send(json.dumps(welcome_msg))
        
    async def unregister_client(self, websocket):
        """Unregister a WebSocket client"""
        self.clients.discard(websocket)
        logger.info(f"🔌 Client disconnected. Total clients: {len(self.clients)}")
        
    async def broadcast_transcription(self, result, confidence: str = "HIGH"):
        """
        Broadcast rich transcription with metadata to all connected clients.
        
        Args:
            result: dict with keys: text, language, emotion, audio_events, raw_text
                    or str (legacy support)
            confidence: confidence level (for backward compatibility)
        """
        if not self.clients:
            return
        
        # Handle legacy string format
        if isinstance(result, str):
            result = {
                'text': result,
                'language': None,
                'emotion': None,
                'audio_events': []
            }
            
        message = {
            "type": "transcription",
            "text": result.get('text', ''),
            "language": result.get('language'),
            "emotion": result.get('emotion'),
            "audio_events": result.get('audio_events', []),
            "has_itn": result.get('has_itn', False),
            "raw_text": result.get('raw_text', ''),
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "source": "npu-sensevoice"
        }
        
        # Send to all connected clients
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister_client(client)
        
        # Format log message with metadata
        log_parts = [result.get('text', '')]
        if result.get('emotion'):
            log_parts.append(f"[{result['emotion']}]")
        if result.get('audio_events'):
            log_parts.append(f"[{', '.join(result['audio_events'])}]")
        
        logger.debug(f"📡 Broadcasted to {len(self.clients)} clients: {' '.join(log_parts)}")
        
    async def broadcast_status(self, status: str, data: dict = None):
        """Broadcast status updates to all connected clients"""
        if not self.clients:
            return
            
        message = {
            "type": "status",
            "message": status,
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }
        
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error sending status to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister_client(client)
            
    async def handle_client(self, websocket, path="/"):
        """Handle WebSocket client connections"""
        logger.info(f"🌐 Client connecting to path: {path}")
        await self.register_client(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from client: {message}")
                except Exception as e:
                    logger.error(f"Error handling client message: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)
            
    async def handle_client_message(self, websocket, data: dict):
        """Handle messages from clients"""
        msg_type = data.get("type", "unknown")
        
        if msg_type == "ping":
            # Respond to ping with pong
            response = {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(response))
        elif msg_type == "status_request":
            # Send current status
            status = {
                "type": "status",
                "message": "NPU transcription service running",
                "timestamp": datetime.now().isoformat(),
                "clients_connected": len(self.clients)
            }
            await websocket.send(json.dumps(status))
        else:
            logger.debug(f"Unknown message type from client: {msg_type}")
            
    def get_handler(self):
        """Get a proper handler function for websockets.serve"""
        async def handler(websocket):
            await self.handle_client(websocket, "/")
        return handler
        
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"🚀 Starting WebSocket server on {self.host}:{self.port}")
        
        # Get a proper handler function
        handler = self.get_handler()
        
        self.server = await websockets.serve(
            handler,
            self.host,
            self.port,
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=10,   # Wait 10 seconds for pong
        )
        
        logger.info(f"✅ WebSocket server running on ws://{self.host}:{self.port}")
        
    async def stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("🛑 WebSocket server stopped")
            
    def get_client_count(self) -> int:
        """Get the number of connected clients"""
        return len(self.clients)

# Global WebSocket server instance
websocket_server = None

def get_websocket_server() -> TranscriptionWebSocketServer:
    """Get the global WebSocket server instance"""
    global websocket_server
    if websocket_server is None:
        websocket_server = TranscriptionWebSocketServer()
    return websocket_server

async def broadcast_transcription(result, confidence: str = "HIGH"):
    """
    Convenience function to broadcast transcription with rich metadata.
    
    Args:
        result: dict with keys: text, language, emotion, audio_events
                or str (legacy support)
    """
    server = get_websocket_server()
    await server.broadcast_transcription(result, confidence)

async def broadcast_status(status: str, data: dict = None):
    """Convenience function to broadcast status"""
    server = get_websocket_server()
    await server.broadcast_status(status, data)