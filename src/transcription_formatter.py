"""
Transcription Formatter
=======================
Handles formatting and output of transcription results with
emojis, metadata, and WebSocket broadcasting.
"""

import logging
import sys
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class TranscriptionFormatter:
    """Formats and emits transcription results"""

    def __init__(self, config: dict, websocket_manager):
        """
        Initialize transcription formatter.
        
        Args:
            config: Configuration dictionary with display settings
            websocket_manager: WebSocket manager for broadcasting
        """
        self.config = config
        self.websocket_manager = websocket_manager
        
        # Display settings
        self.show_emotions = config.get('show_emotions', False)
        self.show_events = config.get('show_events', True)
        self.show_language = config.get('show_language', True)
        
        # Import emoji mappings from decoder
        self._load_emoji_mappings()

    def _load_emoji_mappings(self) -> None:
        """Load emoji mappings from transcription decoder"""
        try:
            from transcription_decoder import EMOTION_TAGS, AUDIO_EVENT_TAGS
            self.emotion_emojis = EMOTION_TAGS
            self.event_emojis = AUDIO_EVENT_TAGS
        except ImportError:
            logger.warning("Could not import emoji mappings from transcription_decoder")
            self.emotion_emojis = {}
            self.event_emojis = {}

    def format_display_text(self, text: str, result: Dict[str, Any]) -> str:
        """
        Build formatted display text with emojis and metadata.
        
        Args:
            text: Base transcription text
            result: Transcription result dictionary with metadata
            
        Returns:
            str: Formatted display text
        """
        display_parts = []
        
        # Add emotion emoji if present and enabled
        if self.show_emotions and result.get('emotion'):
            emoji = self.emotion_emojis.get(result['emotion'], '')
            if emoji:
                display_parts.append(emoji)
        
        # Add audio event emojis if present and enabled
        if self.show_events and result.get('audio_events'):
            for event in result['audio_events']:
                emoji = self.event_emojis.get(event, '')
                if emoji:
                    display_parts.append(emoji)
        
        # Add the transcription text
        display_parts.append(text)
        
        # Add language tag if detected and enabled
        if self.show_language and result.get('language'):
            display_parts.append(f"[{result['language']}]")
        
        return ' '.join(display_parts)

    def check_metadata_filter(self, result: Dict[str, Any]) -> tuple:
        """
        Apply metadata-based filtering (BGM, events, etc.).
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            tuple: (should_filter, filter_reason) - bool and string reason
        """
        # Check if BGM filtering is enabled
        if self.config.get('filter_bgm', False):
            if 'BGM' in result.get('audio_events', []):
                return True, "Background music detected"
        
        # Check for specific event filtering
        filter_events = self.config.get('filter_events', [])
        if filter_events:
            for event in result.get('audio_events', []):
                if event in filter_events:
                    return True, f"Filtered event: {event}"
        
        return False, None

    def emit_transcription(self, display_text: str, result: Dict[str, Any], 
                          new_words: Optional[List[Dict]] = None) -> None:
        """
        Emit transcription to console and WebSocket.
        
        Args:
            display_text: Formatted text to display
            result: Full transcription result dictionary
            new_words: Optional list of new words (for timeline merging)
        """
        # Print to console
        print(f"TRANSCRIPT: {display_text}")
        sys.stdout.flush()
        
        # Update result for WebSocket if using timeline merging
        if new_words is not None:
            result['words'] = new_words
        
        # Broadcast via WebSocket
        self.websocket_manager.broadcast_transcription(result)

    def format_debug_message(self, message: str, level: str = 'info') -> str:
        """
        Format debug message with appropriate prefix.
        
        Args:
            message: Message to format
            level: Log level (info, warning, error, debug)
            
        Returns:
            str: Formatted message
        """
        prefixes = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'debug': '🔍',
            'success': '✅'
        }
        
        prefix = prefixes.get(level, '')
        return f"{prefix} {message}" if prefix else message

    def format_statistics(self, stats: Dict[str, Any]) -> str:
        """
        Format statistics for display.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            str: Formatted statistics string
        """
        lines = []
        lines.append("=" * 50)
        lines.append("TRANSCRIPTION STATISTICS")
        lines.append("=" * 50)
        
        if 'total_chunks' in stats:
            lines.append(f"Total chunks processed: {stats['total_chunks']}")
        
        if 'avg_inference_time' in stats:
            lines.append(f"Avg inference time: {stats['avg_inference_time']:.2f}ms")
        
        if 'total_words' in stats:
            lines.append(f"Total words transcribed: {stats['total_words']}")
        
        if 'errors' in stats:
            lines.append(f"Errors encountered: {stats['errors']}")
        
        lines.append("=" * 50)
        
        return '\n'.join(lines)

    def emit_status(self, status: str, level: str = 'info') -> None:
        """
        Emit a status message.
        
        Args:
            status: Status message
            level: Message level
        """
        formatted = self.format_debug_message(status, level)
        print(formatted)
        sys.stdout.flush()
