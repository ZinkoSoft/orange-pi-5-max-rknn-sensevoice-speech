"""
Audio Stream Manager
====================
Handles all PyAudio stream operations: device detection, initialization, 
sample rate detection, and audio data capture.
"""

import logging
import queue
import numpy as np
import pyaudio

logger = logging.getLogger(__name__)


class AudioStreamManager:
    """Manages PyAudio stream lifecycle and audio device operations"""

    def __init__(self, config: dict):
        """
        Initialize audio stream manager.
        
        Args:
            config: Configuration dictionary with audio settings
        """
        self.config = config
        self.audio = None
        self.stream = None
        self.audio_queue = queue.Queue()
        self.is_recording = False
        
        # Audio settings from config
        self.chunk_size = config['chunk_size']
        self.audio_format = pyaudio.paInt16
        self.target_device = config.get('audio_device')
        
        # Detected stream parameters
        self.device_rate = None
        self.channels = None
        self.device_index = None

    def find_audio_device(self, device_name: str = None) -> int:
        """
        Find audio device by name or return default.
        
        Args:
            device_name: Optional device name to search for
            
        Returns:
            int: Device index
        """
        audio = pyaudio.PyAudio()

        try:
            device_count = audio.get_device_count()
            logger.info(f"Scanning {device_count} audio devices...")

            target_device = None
            devices_found = []

            for i in range(device_count):
                try:
                    device_info = audio.get_device_info_by_index(i)
                    device_name_clean = device_info['name'].strip()
                    devices_found.append(f"Device {i}: {device_name_clean}")

                    if device_info['maxInputChannels'] > 0:
                        if 'AIRHUG' in device_name_clean.upper():
                            target_device = i
                            logger.info(f"Found AIRHUG device: {device_name_clean} (Device {i})")
                            break

                except Exception as e:
                    logger.debug(f"Error checking device {i}: {e}")
                    continue

            logger.info("Available audio devices:")
            for device in devices_found:
                logger.info(f"  {device}")

            if target_device is None:
                default_device = audio.get_default_input_device_info()
                target_device = default_device['index']
                logger.info(f"AIRHUG not found, using default: {default_device['name']} (Device {target_device})")

            return target_device

        finally:
            audio.terminate()

    def detect_sample_rate(self, device_index: int) -> int:
        """
        Auto-detect supported sample rate for device.
        
        Args:
            device_index: Device index to test
            
        Returns:
            int: Supported sample rate in Hz
        """
        audio = pyaudio.PyAudio()

        try:
            device_info = audio.get_device_info_by_index(device_index)
            logger.info(f"Device info: {device_info['name']}")
            logger.info(f"   Default sample rate: {device_info['defaultSampleRate']}")

            test_rates = [16000, 44100, 48000, 22050, 8000]

            for rate in test_rates:
                try:
                    audio.is_format_supported(
                        rate, input_device=device_index,
                        input_channels=1, input_format=pyaudio.paInt16
                    )
                    logger.info(f"Sample rate {rate}Hz supported")
                    return rate
                except ValueError:
                    logger.debug(f"Sample rate {rate}Hz not supported")
                    continue

            default_rate = int(device_info['defaultSampleRate'])
            logger.warning(f"Using device default sample rate: {default_rate}Hz")
            return default_rate

        finally:
            audio.terminate()

    def pick_stream_params(self, device_index: int) -> tuple:
        """
        Return supported (rate, channels) for device.
        
        Args:
            device_index: Device index to test
            
        Returns:
            tuple: (sample_rate, channels)
        """
        audio = pyaudio.PyAudio()
        try:
            rates = [16000, 48000, 44100, 32000, 22050, 8000]
            chans = [1, 2]
            for ch in chans:
                for r in rates:
                    try:
                        audio.is_format_supported(
                            r, input_device=device_index,
                            input_channels=ch, input_format=pyaudio.paInt16
                        )
                        logger.info(f"Device supports {r} Hz, {ch} ch")
                        return r, ch
                    except ValueError:
                        continue

            # Fallback to device defaults
            info = audio.get_device_info_by_index(device_index)
            r = int(info.get('defaultSampleRate', 48000))
            ch = 1 if info.get('maxInputChannels', 1) >= 1 else info.get('maxInputChannels', 1)
            logger.warning(f"Falling back to device defaults: {r} Hz, {ch} ch")
            return r, ch
        finally:
            audio.terminate()

    def audio_callback(self, in_data, frame_count, time_info, status):
        """
        Audio input callback for PyAudio stream.
        
        Args:
            in_data: Raw audio data bytes
            frame_count: Number of frames
            time_info: Timing information
            status: Stream status flags
            
        Returns:
            tuple: (data, continue_flag)
        """
        if self.is_recording:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def initialize_stream(self) -> bool:
        """
        Initialize PyAudio stream with auto-detected parameters.
        
        Returns:
            bool: True if successful
        """
        try:
            # Find audio device
            self.device_index = self.find_audio_device(self.target_device)
            if self.device_index is None:
                logger.error("No suitable audio device found")
                return False

            # Auto-detect sample rate and channels
            detected_rate = self.detect_sample_rate(self.device_index)
            self.device_rate, self.channels = self.pick_stream_params(self.device_index)

            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()

            # Open audio stream
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.device_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback
            )

            logger.info(f"Audio stream initialized: {self.device_rate} Hz, {self.channels} ch (Device {self.device_index})")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize audio stream: {e}")
            return False

    def start_recording(self) -> bool:
        """
        Start recording audio.
        
        Returns:
            bool: True if successful
        """
        try:
            if not self.stream:
                logger.error("Stream not initialized")
                return False

            self.is_recording = True
            self.stream.start_stream()
            logger.info("Audio recording started")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> None:
        """Stop recording audio and cleanup resources"""
        logger.info("Stopping audio recording...")
        
        self.is_recording = False

        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")

        logger.info("Audio recording stopped")

    def get_audio_chunk(self, timeout: float = 0.1) -> np.ndarray:
        """
        Get next audio chunk from queue.
        
        Args:
            timeout: Queue timeout in seconds
            
        Returns:
            np.ndarray: Audio data or None if timeout
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_stream_info(self) -> dict:
        """
        Get current stream information.
        
        Returns:
            dict: Stream parameters
        """
        return {
            'device_rate': self.device_rate,
            'channels': self.channels,
            'device_index': self.device_index,
            'is_recording': self.is_recording
        }
