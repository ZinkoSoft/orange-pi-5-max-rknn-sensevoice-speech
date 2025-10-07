#!/usr/bin/env python3
"""
Simple HTTP server to serve the web interface for live transcription
"""

import os
import sys
import http.server
import socketserver
import threading
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranscriptionHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for the transcription web interface"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve from
        web_dir = Path(__file__).parent.parent / "web"
        super().__init__(*args, directory=str(web_dir), **kwargs)
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

class TranscriptionWebServer:
    """Simple web server for the transcription interface"""
    
    def __init__(self, port=8080, host="0.0.0.0"):
        self.port = port
        self.host = host
        self.httpd = None
        self.server_thread = None
        
    def start_server(self):
        """Start the web server in a separate thread"""
        try:
            self.httpd = socketserver.TCPServer(
                (self.host, self.port), 
                TranscriptionHTTPHandler
            )
            
            logger.info(f"🌐 Starting web server on http://{self.host}:{self.port}")
            
            # Start server in a separate thread
            self.server_thread = threading.Thread(
                target=self.httpd.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            logger.info(f"✅ Web server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start web server: {e}")
            return False
    
    def stop_server(self):
        """Stop the web server"""
        if self.httpd:
            logger.info("🛑 Stopping web server...")
            self.httpd.shutdown()
            self.httpd.server_close()
            
        if self.server_thread:
            self.server_thread.join(timeout=5.0)
            
        logger.info("✅ Web server stopped")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Transcription Web Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    
    args = parser.parse_args()
    
    # Check if web directory exists
    web_dir = Path(__file__).parent.parent / "web"
    if not web_dir.exists():
        logger.error(f"❌ Web directory not found: {web_dir}")
        sys.exit(1)
    
    index_file = web_dir / "index.html"
    if not index_file.exists():
        logger.error(f"❌ Index file not found: {index_file}")
        sys.exit(1)
    
    # Start the server
    server = TranscriptionWebServer(port=args.port, host=args.host)
    
    if not server.start_server():
        sys.exit(1)
    
    try:
        logger.info("🎯 Web interface available - navigate to the transcription dashboard")
        logger.info("Press Ctrl+C to stop the server")
        
        # Keep the main thread alive
        while True:
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🔔 Received shutdown signal")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()