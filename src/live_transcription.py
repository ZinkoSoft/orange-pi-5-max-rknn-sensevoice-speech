#!/usr/bin/env python3
"""
🎙️ Enhanced NPU-Accelerated SenseVoice Live Transcription
========================================================
Production-ready live transcription with NPU acceleration, caching, and monitoring.
"""

import os
import re
from collections import deque
import sys
import time
import logging
import threading
import queue
import signal
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import pyaudio
import sentencepiece as spm
import kaldi_native_fbank as knf
from rknnlite.api import RKNNLite
from websocket_server import get_websocket_server, broadcast_transcription, broadcast_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/transcription.log')
    ]
)
logger = logging.getLogger(__name__)

# SenseVoice constants
RKNN_INPUT_LEN = 171
SPEECH_SCALE = 1/2  # For fp16 inference to prevent overflow

# Language mapping
LANGUAGES = {"auto": 0, "zh": 3, "en": 4, "yue": 7, "ja": 11, "ko": 12, "nospeech": 13}

class WavFrontend:
    """SenseVoice frontend for proper feature extraction"""
    
    def __init__(self, cmvn_file: str = None, fs: int = 16000, n_mels: int = 80, 
                 frame_length: int = 25, frame_shift: int = 10, lfr_m: int = 7, lfr_n: int = 6):
        opts = knf.FbankOptions()
        opts.frame_opts.samp_freq = fs
        opts.frame_opts.dither = 0
        opts.frame_opts.window_type = "hamming"
        opts.frame_opts.frame_shift_ms = float(frame_shift)
        opts.frame_opts.frame_length_ms = float(frame_length)
        opts.mel_opts.num_bins = n_mels
        opts.energy_floor = 0
        opts.frame_opts.snip_edges = True
        opts.mel_opts.debug_mel = False
        self.opts = opts
        
        self.lfr_m = lfr_m
        self.lfr_n = lfr_n
        self.cmvn_file = cmvn_file
        
        if self.cmvn_file and Path(self.cmvn_file).exists():
            self.cmvn = self.load_cmvn()
        else:
            self.cmvn = None
    
    def fbank(self, waveform: np.ndarray):
        """Extract fbank features"""
        waveform = waveform * (1 << 15)
        fbank_fn = knf.OnlineFbank(self.opts)
        fbank_fn.accept_waveform(self.opts.frame_opts.samp_freq, waveform.tolist())
        frames = fbank_fn.num_frames_ready
        mat = np.empty([frames, self.opts.mel_opts.num_bins])
        for i in range(frames):
            mat[i, :] = fbank_fn.get_frame(i)
        feat = mat.astype(np.float32)
        return feat
    
    def apply_lfr(self, inputs: np.ndarray, lfr_m: int, lfr_n: int) -> np.ndarray:
        """Apply Low Frame Rate processing"""
        LFR_inputs = []
        T = inputs.shape[0]
        T_lfr = int(np.ceil(T / lfr_n))
        left_padding = np.tile(inputs[0], ((lfr_m - 1) // 2, 1))
        inputs = np.vstack((left_padding, inputs))
        T = T + (lfr_m - 1) // 2
        
        for i in range(T_lfr):
            if lfr_m <= T - i * lfr_n:
                LFR_inputs.append((inputs[i * lfr_n : i * lfr_n + lfr_m]).reshape(1, -1))
            else:
                # process last LFR frame
                num_padding = lfr_m - (T - i * lfr_n)
                frame = inputs[i * lfr_n :].reshape(-1)
                for _ in range(num_padding):
                    frame = np.hstack((frame, inputs[-1]))
                LFR_inputs.append(frame)
        
        LFR_outputs = np.vstack(LFR_inputs).astype(np.float32)
        return LFR_outputs
    
    def apply_cmvn(self, inputs: np.ndarray) -> np.ndarray:
        """Apply CMVN normalization"""
        if self.cmvn is None:
            return inputs
        
        frame, dim = inputs.shape
        means = np.tile(self.cmvn[0:1, :dim], (frame, 1))
        vars = np.tile(self.cmvn[1:2, :dim], (frame, 1))
        inputs = (inputs + means) * vars
        return inputs
    
    def get_features(self, inputs: np.ndarray) -> np.ndarray:
        """Complete feature extraction pipeline"""
        fbank = self.fbank(inputs)
        feats = self.apply_cmvn(self.apply_lfr(fbank, self.lfr_m, self.lfr_n))
        return feats
    
    def load_cmvn(self) -> np.ndarray:
        """Load CMVN parameters"""
        with open(self.cmvn_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        means_list = []
        vars_list = []
        for i in range(len(lines)):
            line_item = lines[i].split()
            if line_item[0] == "<AddShift>":
                line_item = lines[i + 1].split()
                if line_item[0] == "<LearnRateCoef>":
                    add_shift_line = line_item[3 : (len(line_item) - 1)]
                    means_list = list(add_shift_line)
                    continue
            elif line_item[0] == "<Rescale>":
                line_item = lines[i + 1].split()
                if line_item[0] == "<LearnRateCoef>":
                    rescale_line = line_item[3 : (len(line_item) - 1)]
                    vars_list = list(rescale_line)
                    continue
        
        means = np.array(means_list).astype(np.float64)
        vars = np.array(vars_list).astype(np.float64)
        cmvn = np.array([means, vars])
        return cmvn

class NPUSenseVoiceTranscriber:
    """Enhanced NPU-accelerated SenseVoice transcriber with caching and monitoring"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize transcriber with configuration"""
        self.config = config or self._load_config()
        self.rknn = None
        self.sp = None  # SentencePiece tokenizer
        self.embedding = None  # Language/query embeddings
        self.blank_id = 0  # Blank token ID for CTC decoding
        self.frontend = None  # Feature extraction frontend
        self.websocket_server = None  # WebSocket server for streaming
        self.websocket_task = None  # WebSocket server task
        self.noise_floor = None
        self.rms_margin = 1.8e-3      # tweakable; ~ -55 dBFS region for 16-bit
        self.min_chars = 3            # require at least this many alnum chars
        self.last_texts = deque(maxlen=4)
        self.duplicate_cooldown_s = 4.0
        self._last_emit_ts = 0.0
        self.model_rate = 16000          # what SenseVoice expects
        self.device_rate = None          # detected at runtime
        self.rms_margin = float(os.getenv('RMS_MARGIN', '0.004'))
        self.noise_floor = None
        self.noise_calib_secs = float(os.getenv('NOISE_CALIB_SECS', '1.5'))
        
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stats = {
            'total_chunks_processed': 0,
            'total_inference_time': 0.0,
            'average_inference_time': 0.0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Audio settings from config
        self.sample_rate = self.config.get('sample_rate', 16000)
        self.chunk_size = self.config.get('chunk_size', 1024)
        self.channels = self.config.get('channels', 1)
        self.audio_format = pyaudio.paInt16
        
        # Processing settings
        self.mel_bins = self.config.get('mel_bins', 80)
        self.max_frames = self.config.get('max_frames', 3000)
        self.chunk_duration = self.config.get('chunk_duration', 3.0)
        self.overlap_duration = self.config.get('overlap_duration', 1.5)
        
        # Model settings
        self.model_path = self.config.get('model_path', '/app/models/sensevoice-rknn/sense-voice-encoder.rknn')
        self.embedding_path = self.config.get('embedding_path', '/app/models/sensevoice-rknn/embedding.npy')
        self.bpe_path = self.config.get('bpe_path', '/app/models/sensevoice-rknn/chn_jpn_yue_eng_ko_spectok.bpe.model')
        self.cmvn_path = self.config.get('cmvn_path', '/app/models/sensevoice-rknn/am.mvn')
        self.language = self.config.get('language', 'auto')
        self.use_itn = self.config.get('use_itn', True)
        
        logger.info("🚀 Initializing Enhanced NPU SenseVoice Transcriber")
        self._validate_config()
        self._load_model()
        self._load_tokenizer()
        self._setup_websocket_server()
    
    def _rms(self, x: np.ndarray) -> float:
        x = x.astype(np.float32) / 32768.0 if x.dtype == np.int16 else x.astype(np.float32)
        return float(np.sqrt(np.mean(x * x) + 1e-12))

    def _calibrate_noise_floor(self, timeout_s=1.0) -> None:
        """Collect ~1 second of audio from queue to estimate ambient RMS."""
        logger.info("📏 Calibrating noise floor… stay quiet for ~1s")
        buf = []
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                buf.append(self.audio_queue.get(timeout=timeout_s))
            except queue.Empty:
                break
        if buf:
            rms = self._rms(np.concatenate(buf))
            self.noise_floor = rms
            logger.info(f"✅ Noise floor: {rms:.6f} RMS")
        else:
            # fallback to a conservative small value
            self.noise_floor = 1.0e-3
            logger.info(f"⚠️ Noise floor fallback: {self.noise_floor:.6f} RMS")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment and defaults"""
        return {
            'sample_rate': 16000,
            'chunk_size': 1024,
            'channels': 1,
            'mel_bins': 80,
            'max_frames': 3000,
            'chunk_duration': float(os.getenv('CHUNK_DURATION', '3.0')),
            'overlap_duration': float(os.getenv('OVERLAP_DURATION', '1.5')),
            'model_path': os.getenv('MODEL_PATH', '/app/models/sensevoice-rknn/sense-voice-encoder.rknn'),
            'embedding_path': os.getenv('EMBEDDING_PATH', '/app/models/sensevoice-rknn/embedding.npy'),
            'bpe_path': os.getenv('BPE_PATH', '/app/models/sensevoice-rknn/chn_jpn_yue_eng_ko_spectok.bpe.model'),
            'cmvn_path': os.getenv('CMVN_PATH', '/app/models/sensevoice-rknn/am.mvn'),
            'language': os.getenv('LANGUAGE', 'auto'),
            'use_itn': os.getenv('USE_ITN', 'true').lower() == 'true',
            'audio_device': os.getenv('AUDIO_DEVICE', 'default'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'websocket_port': int(os.getenv('WEBSOCKET_PORT', '8765')),
            'websocket_host': os.getenv('WEBSOCKET_HOST', '0.0.0.0')
        }
    
    def _validate_config(self):
        """Validate configuration and model availability"""
        model_path = Path(self.model_path)
        if not model_path.exists():
            logger.error(f"❌ Model file not found: {self.model_path}")
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        model_size = model_path.stat().st_size
        expected_size = 485 * 1024 * 1024  # ~485MB
        if abs(model_size - expected_size) > expected_size * 0.1:  # 10% tolerance
            logger.warning(f"⚠️ Model size unexpected: {model_size / 1024 / 1024:.1f}MB")
        
        logger.info(f"✅ Model validation passed: {model_size / 1024 / 1024:.1f}MB")
    
    def _load_model(self):
        """Load and initialize RKNN model"""
        try:
            logger.info(f"📥 Loading RKNN model: {self.model_path}")
            
            self.rknn = RKNNLite()
            
            # Load model
            ret = self.rknn.load_rknn(self.model_path)
            if ret != 0:
                raise RuntimeError(f"Failed to load RKNN model: {ret}")
            
            # Initialize runtime
            ret = self.rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0_1_2)
            if ret != 0:
                raise RuntimeError(f"Failed to initialize RKNN runtime: {ret}")
            
            logger.info("✅ NPU model loaded and initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Model loading failed: {e}")
            raise
    
    def _load_tokenizer(self):
        """Load BPE tokenizer and embedding for text decoding"""
        try:
            logger.info(f"📥 Loading SentencePiece tokenizer: {self.bpe_path}")
            
            # Validate tokenizer file exists
            if not Path(self.bpe_path).exists():
                raise FileNotFoundError(f"BPE model not found: {self.bpe_path}")
            
            # Load SentencePiece tokenizer
            self.sp = spm.SentencePieceProcessor()
            self.sp.load(self.bpe_path)
            
            logger.info(f"✅ Tokenizer loaded successfully, vocab size: {self.sp.vocab_size()}")
            
            # Load embedding
            logger.info(f"📥 Loading embeddings: {self.embedding_path}")
            
            if not Path(self.embedding_path).exists():
                raise FileNotFoundError(f"Embedding file not found: {self.embedding_path}")
            
            self.embedding = np.load(self.embedding_path)
            logger.info(f"✅ Embeddings loaded: {self.embedding.shape}")
            
            # Initialize frontend for feature extraction
            logger.info(f"📥 Loading frontend with CMVN: {self.cmvn_path}")
            self.frontend = WavFrontend(cmvn_file=self.cmvn_path, fs=self.model_rate)
            logger.info("✅ Frontend initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Tokenizer/embedding loading failed: {e}")
            raise
    
    def _setup_websocket_server(self):
        """Setup WebSocket server for streaming transcriptions"""
        try:
            self.websocket_server = get_websocket_server()
            self.websocket_server.host = self.config.get('websocket_host', '0.0.0.0')
            self.websocket_server.port = self.config.get('websocket_port', 8765)
            logger.info(f"📡 WebSocket server configured on {self.websocket_server.host}:{self.websocket_server.port}")
        except Exception as e:
            logger.error(f"❌ WebSocket server setup failed: {e}")
            raise
    
    def _start_websocket_server(self):
        """Start WebSocket server in a separate thread"""
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
            time.sleep(1.0)
            logger.info(f"✅ WebSocket server started on ws://{self.websocket_server.host}:{self.websocket_server.port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            # Continue without WebSocket streaming
            self.websocket_server = None
    
    def _audio_to_features(self, audio_data: np.ndarray) -> Optional[np.ndarray]:
        """Convert audio to SenseVoice features with query embeddings"""
        try:
            # Convert to float32 and normalize for SenseVoice
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            
            # Extract proper SenseVoice features using frontend
            speech_features = self.frontend.get_features(audio_data)
            
            # Limit to reasonable sequence length
            if speech_features.shape[0] > self.max_frames:
                speech_features = speech_features[:self.max_frames, :]
            
            # Add language and text normalization queries (based on reference implementation)
            language_id = LANGUAGES.get(self.language, 0)  # Default to auto
            language_query = self.embedding[[[language_id]]]
            
            # 14 means with itn, 15 means without itn
            text_norm_query = self.embedding[[[14 if self.use_itn else 15]]]
            event_emo_query = self.embedding[[[1, 2]]]
            
            # Scale the speech features
            speech_features = speech_features[None, :, :].astype(np.float32) * SPEECH_SCALE
            
            # Concatenate queries with speech features
            input_content = np.concatenate([
                language_query,
                event_emo_query, 
                text_norm_query,
                speech_features,
            ], axis=1).astype(np.float32)
            
            # Pad to RKNN_INPUT_LEN if needed
            if input_content.shape[1] < RKNN_INPUT_LEN:
                padding = RKNN_INPUT_LEN - input_content.shape[1]
                input_content = np.pad(input_content, ((0, 0), (0, padding), (0, 0)), mode='constant')
            elif input_content.shape[1] > RKNN_INPUT_LEN:
                input_content = input_content[:, :RKNN_INPUT_LEN, :]
            
            logger.debug(f"🎯 Model input shape: {input_content.shape}")
            
            return input_content
            
        except Exception as e:
            logger.error(f"❌ Audio preprocessing error: {e}")
            self.stats['errors'] += 1
            return None
    
    def _npu_inference(self, mel_input: np.ndarray) -> Optional[np.ndarray]:
        """Run inference on NPU cores"""
        try:
            start_time = time.time()
            
            # Run NPU inference
            outputs = self.rknn.inference(inputs=[mel_input])
            
            inference_time = (time.time() - start_time) * 1000
            
            # Update statistics
            self.stats['total_chunks_processed'] += 1
            self.stats['total_inference_time'] += inference_time
            self.stats['average_inference_time'] = (
                self.stats['total_inference_time'] / self.stats['total_chunks_processed']
            )
            
            if outputs is None or len(outputs) == 0:
                logger.error("❌ NPU inference returned no outputs")
                self.stats['errors'] += 1
                return None
            
            logger.info(f"🚀 NPU Inference: {inference_time:.1f}ms | "
                       f"Output: {outputs[0].shape} | "
                       f"Avg: {self.stats['average_inference_time']:.1f}ms")
            
            return outputs[0]
            
        except Exception as e:
            logger.error(f"❌ NPU inference error: {e}")
            self.stats['errors'] += 1
            return None
    
    def _decode_output(self, output_tensor: np.ndarray) -> Optional[str]:
        """
        Decode NPU output -> text with:
        - CTC argmax + collapse
        - blank-probability gate
        - meta-token stripping
        - duplicate suppression
        """
        try:
            def unique_consecutive(arr):
                if len(arr) == 0:
                    return arr
                mask = np.append([True], arr[1:] != arr[:-1])
                out = arr[mask]
                return out[out != self.blank_id].tolist()

            if output_tensor.ndim != 3:
                logger.error(f"Unexpected output tensor shape: {output_tensor.shape}")
                return None

            # logits shape [1, vocab, T]
            logits = output_tensor[0]  # [vocab, T]

            # --- Gate by blank posterior without full softmax on entire vocab
            # compute softmax across vocab (ok at this size; T is small)
            # logits are float16/32; be numerically safe
            m = np.max(logits, axis=0, keepdims=True)
            exp = np.exp(logits - m)
            probs = exp / np.sum(exp, axis=0, keepdims=True)          # [vocab, T]
            blank_prob = probs[self.blank_id, :]                       # [T]
            avg_blank = float(np.mean(blank_prob))
            if avg_blank > 0.97:
                logger.debug(f"🔇 Drop by blank gate (avg_blank={avg_blank:.3f})")
                return None

            # --- Argmax decode (CTC)
            ids = np.argmax(logits, axis=0)                           # [T]
            ids = unique_consecutive(ids)

            if not ids:
                return None

            text = self.sp.DecodeIds(ids).strip()

            # --- Strip SenseVoice meta tokens like <|en|><|BGM|><|withitn|>
            text_clean = re.sub(r"<\|.*?\|>", "", text).strip()

            # --- Require some real alphanumeric content
            alnum = re.findall(r"[A-Za-z0-9]", text_clean)
            if len(alnum) < self.min_chars:
                logger.debug(f"🔇 Too little content after cleanup: '{text_clean}'")
                return None

            # --- Duplicate suppression within a short window
            now = time.time()
            if text_clean in self.last_texts and (now - self._last_emit_ts) < self.duplicate_cooldown_s:
                logger.debug(f"🔁 Suppress duplicate: '{text_clean}'")
                return None

            self.last_texts.append(text_clean)
            self._last_emit_ts = now
            logger.info(f"📝 Transcription: {text_clean}")
            return text_clean

        except Exception as e:
            logger.error(f"❌ Text decoding error: {e}")
            self.stats['errors'] += 1
            return None
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio input callback"""
        if self.is_recording:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def _pick_stream_params(self, device_index: int):
        """Return a supported (rate, channels) for the input device."""
        audio = pyaudio.PyAudio()
        try:
            # Prefer mono; try common rates
            rates = [16000, 48000, 44100, 32000, 22050, 8000]
            chans = [1, 2]
            for ch in chans:
                for r in rates:
                    try:
                        audio.is_format_supported(
                            r,
                            input_device=device_index,
                            input_channels=ch,
                            input_format=pyaudio.paInt16
                        )
                        logger.info(f"✅ Device supports {r} Hz, {ch} ch")
                        return r, ch
                    except ValueError:
                        continue
            # Fallback to device defaults if nothing matched
            info = audio.get_device_info_by_index(device_index)
            r = int(info.get('defaultSampleRate', 48000))
            ch = 1 if info.get('maxInputChannels', 1) >= 1 else info.get('maxInputChannels', 1)
            logger.warning(f"⚠️ Falling back to device defaults: {r} Hz, {ch} ch")
            return r, ch
        finally:
            audio.terminate()
    
    def _process_audio_worker(self):
        audio_buffer = np.array([], dtype=np.int16)

        # size thresholds in DEVICE samples
        dev_rate = int(self.device_rate or self.sample_rate or 16000)
        buffer_size_dev = int(dev_rate * self.chunk_duration)
        overlap_size_dev = int(dev_rate * self.overlap_duration)

        logger.info(f"🎙️ Audio worker started | Buffer: {self.chunk_duration}s | Overlap: {self.overlap_duration}s | dev={dev_rate}Hz → model={self.model_rate}Hz")

        # simple noise-floor bootstrap (first N seconds)
        calib_needed = int(dev_rate * self.noise_calib_secs)
        rms_accum = []
        seen_for_calib = 0
        
        while self.is_recording:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                audio_buffer = np.concatenate([audio_buffer, chunk])

                # bootstrap noise floor from the first ~N seconds of audio
                if self.noise_floor is None and seen_for_calib < calib_needed:
                    sample = audio_buffer[:min(len(audio_buffer), calib_needed)]
                    # use device-rate RMS (cheap and good enough)
                    rms_accum.append(self._rms(sample))
                    seen_for_calib = len(sample)
                    if seen_for_calib >= calib_needed:
                        self.noise_floor = float(np.median(rms_accum))
                        logger.info(f"🎚️ Calibrated noise floor = {self.noise_floor:.6f} (over {self.noise_calib_secs:.1f}s)")
                    continue

                if len(audio_buffer) < buffer_size_dev:
                    continue

                # --- we have ~chunk_duration seconds at DEVICE rate ---
                # quick resample sanity logging
                secs_in = len(audio_buffer) / dev_rate
                x16 = self._resample_to_model(audio_buffer)
                secs_out = len(x16) / float(self.model_rate)

                # energy gate (use model-rate signal for consistency)
                rms = self._rms(x16)
                if self.noise_floor is not None and rms < (self.noise_floor + self.rms_margin):
                    logger.debug(f"🔇 Skip: RMS {rms:.6f} < floor {self.noise_floor:.6f} + {self.rms_margin:.6f}")
                    audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)
                    continue

                # → features @16k
                mel_input = self._audio_to_features(x16)

                if mel_input is not None:
                    npu_output = self._npu_inference(mel_input)
                    if npu_output is not None:
                        transcription = self._decode_output(npu_output)
                        if transcription is not None:
                            print(f"TRANSCRIPT: {transcription}")
                            sys.stdout.flush()
                            if hasattr(self, 'websocket_loop') and self.websocket_loop:
                                asyncio.run_coroutine_threadsafe(
                                    broadcast_transcription(transcription), self.websocket_loop
                                )

                # keep overlap in DEVICE samples
                audio_buffer = audio_buffer[-overlap_size_dev:] if overlap_size_dev > 0 else np.array([], dtype=np.int16)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Audio processing error: {e}")
                self.stats['errors'] += 1

    def _find_audio_device(self, device_name: str = None) -> Optional[int]:
        """Find audio device by name"""
        audio = pyaudio.PyAudio()
        
        try:
            device_count = audio.get_device_count()
            logger.info(f"🎙️ Scanning {device_count} audio devices...")
            
            target_device = None
            devices_found = []
            
            for i in range(device_count):
                try:
                    device_info = audio.get_device_info_by_index(i)
                    device_name_clean = device_info['name'].strip()
                    devices_found.append(f"Device {i}: {device_name_clean}")
                    
                    # Check if this is an input device
                    if device_info['maxInputChannels'] > 0:
                        # Look for AIRHUG device first
                        if 'AIRHUG' in device_name_clean.upper():
                            target_device = i
                            logger.info(f"🎯 Found AIRHUG device: {device_name_clean} (Device {i})")
                            break
                            
                except Exception as e:
                    logger.debug(f"Error checking device {i}: {e}")
                    continue
            
            # Log all found devices for debugging
            logger.info("📱 Available audio devices:")
            for device in devices_found:
                logger.info(f"  {device}")
            
            # If no AIRHUG device found, use default
            if target_device is None:
                default_device = audio.get_default_input_device_info()
                target_device = default_device['index']
                logger.info(f"⚠️ AIRHUG not found, using default: {default_device['name']} (Device {target_device})")
            
            return target_device
            
        finally:
            audio.terminate()

    def _resample_to_model(self, x_int16: np.ndarray) -> np.ndarray:
        x = x_int16.astype(np.float32) / 32768.0
        if self.device_rate == self.model_rate or self.device_rate is None:
            return x
        try:
            import soxr
            y = soxr.resample(x, self.device_rate, self.model_rate)
            used = "soxr"
        except Exception:
            import librosa
            y = librosa.resample(y=x, orig_sr=self.device_rate, target_sr=self.model_rate, res_type="kaiser_fast")
            used = "librosa"
        self._last_resample_used = used
        return y
 
    def _rms(self, x: np.ndarray) -> float:
        x = x.astype(np.float32)
        return float(np.sqrt(np.mean(x * x)) + 1e-12)

    def _get_device_sample_rate(self, device_index: int) -> int:
        """Auto-detect supported sample rate for device"""
        audio = pyaudio.PyAudio()
        
        try:
            device_info = audio.get_device_info_by_index(device_index)
            logger.info(f"🔍 Device info: {device_info['name']}")
            logger.info(f"   Default sample rate: {device_info['defaultSampleRate']}")
            
            # Test common sample rates
            test_rates = [16000, 44100, 48000, 22050, 8000]
            
            for rate in test_rates:
                try:
                    # Test if this sample rate is supported
                    audio.is_format_supported(
                        rate,
                        input_device=device_index,
                        input_channels=1,
                        input_format=pyaudio.paInt16
                    )
                    logger.info(f"✅ Sample rate {rate}Hz supported")
                    return rate
                except ValueError:
                    logger.debug(f"❌ Sample rate {rate}Hz not supported")
                    continue
            
            # Fallback to device default
            default_rate = int(device_info['defaultSampleRate'])
            logger.warning(f"⚠️ Using device default sample rate: {default_rate}Hz")
            return default_rate
            
        finally:
            audio.terminate()

    def start_transcription(self):
        """Start live transcription with WebSocket streaming"""
        try:
            # Start WebSocket server in separate thread
            self._start_websocket_server()
            
            # Find audio device
            device_index = self._find_audio_device(self.config.get('audio_device'))
            if device_index is None:
                raise RuntimeError("No suitable audio device found")
            
            # Auto-detect sample rate
            detected_sample_rate = self._get_device_sample_rate(device_index)
            self.device_rate = int(detected_sample_rate)
            logger.info(f"🎛️ Device rate set to {self.device_rate} Hz; model rate = {self.model_rate} Hz")
            
            # Pick params the device actually supports
            self.device_rate, self.channels = self._pick_stream_params(device_index)
            logger.info(f"🎛️ Using device params: {self.device_rate} Hz, {self.channels} ch; model rate = {self.model_rate} Hz")

            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()

            
            # Open stream at the *device* rate/channels; we resample to 16k later
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.device_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )

            logger.info(f"🎙️ Audio stream opened: {self.device_rate} Hz, {self.channels} ch (Device {device_index})")
            
            # Start recording
            self.is_recording = True
            self.stream.start_stream()

            # NEW: calibrate before worker starts processing
            self._calibrate_noise_floor(timeout_s=1.0)

            # then start worker
            self.worker_thread = threading.Thread(target=self._process_audio_worker, daemon=True)
            self.worker_thread.start()
            
            logger.info("✅ Live transcription started! Speak into the microphone...")
            logger.info("Press Ctrl+C to stop")
            
            # Keep running until interrupted
            try:
                while self.is_recording:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received")
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            raise
        finally:
            self.stop_transcription()

    def stop_transcription(self):
        """Stop live transcription"""
        logger.info("🛑 Stopping transcription...")
        
        self.is_recording = False
        
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
        
        if hasattr(self, 'worker_thread') and self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        
        # Stop WebSocket server
        if hasattr(self, 'websocket_loop') and self.websocket_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.websocket_server.stop_server(), 
                    self.websocket_loop
                ).result(timeout=5.0)
                self.websocket_loop.call_soon_threadsafe(self.websocket_loop.stop)
            except Exception as e:
                logger.debug(f"WebSocket cleanup error: {e}")
        
        if hasattr(self, 'websocket_thread') and self.websocket_thread:
            self.websocket_thread.join(timeout=5.0)
        
        # Print final statistics
        total_time = time.time() - self.stats['start_time']
        logger.info(f"📊 Session Statistics:")
        logger.info(f"   Total time: {total_time:.1f}s")
        logger.info(f"   Chunks processed: {self.stats['total_chunks_processed']}")
        logger.info(f"   Average inference: {self.stats['average_inference_time']:.1f}ms")
        logger.info(f"   Errors: {self.stats['errors']}")
        
        logger.info("✅ Transcription stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"🔔 Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main application entry point"""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create and start transcriber
        transcriber = NPUSenseVoiceTranscriber()
        transcriber.start_transcription()
        
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()