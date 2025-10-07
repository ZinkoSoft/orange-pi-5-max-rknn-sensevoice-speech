#!/usr/bin/env python3
"""
Audio Processing Module
========================
Handles audio input, feature extraction, and preprocessing for SenseVoice.
"""

import numpy as np
from typing import Optional, Tuple
import logging
import kaldi_native_fbank as knf

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

        if self.cmvn_file and self.cmvn_file.exists():
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
        from pathlib import Path
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

class AudioProcessor:
    """Handles audio processing, resampling, and feature extraction"""

    def __init__(self, config: dict):
        self.config = config
        self.model_rate = 16000  # SenseVoice expects 16kHz
        self.device_rate = None
        self.frontend = None
        self.embedding = None
        self._last_resample_used = None

        # Initialize frontend
        self._init_frontend()

    def _init_frontend(self) -> None:
        """Initialize the audio frontend"""
        from pathlib import Path
        cmvn_path = Path(self.config['cmvn_path'])
        self.frontend = WavFrontend(
            cmvn_file=cmvn_path if cmvn_path.exists() else None,
            fs=self.model_rate,
            n_mels=self.config['mel_bins']
        )
        logger.info("✅ Audio frontend initialized")

    def load_embeddings(self, embedding_path: str) -> bool:
        """Load language and task embeddings"""
        try:
            from pathlib import Path
            if not Path(embedding_path).exists():
                logger.error(f"❌ Embedding file not found: {embedding_path}")
                return False

            self.embedding = np.load(embedding_path)
            logger.info(f"✅ Embeddings loaded: {self.embedding.shape}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load embeddings: {e}")
            return False

    def set_device_rate(self, rate: int) -> None:
        """Set the device sample rate for resampling"""
        self.device_rate = rate
        logger.info(f"🎛️ Device rate set to {self.device_rate} Hz; model rate = {self.model_rate} Hz")

    def resample_to_model_rate(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample audio data to model rate (16kHz)"""
        if self.device_rate == self.model_rate or self.device_rate is None:
            return audio_data.astype(np.float32) / 32768.0

        try:
            # Try soxr first (higher quality)
            import soxr
            x = audio_data.astype(np.float32) / 32768.0
            y = soxr.resample(x, self.device_rate, self.model_rate)
            self._last_resample_used = "soxr"
            return y
        except ImportError:
            # Fallback to librosa
            import librosa
            x = audio_data.astype(np.float32) / 32768.0
            y = librosa.resample(y=x, orig_sr=self.device_rate, target_sr=self.model_rate, res_type="kaiser_fast")
            self._last_resample_used = "librosa"
            return y

    def calculate_rms(self, audio_data: np.ndarray) -> float:
        """Calculate RMS of audio data"""
        x = audio_data.astype(np.float32)
        if x.dtype == np.int16:
            x = x / 32768.0
        return float(np.sqrt(np.mean(x * x) + 1e-12))

    def audio_to_features(self, audio_data: np.ndarray, language: str = 'auto',
                         use_itn: bool = True) -> Optional[np.ndarray]:
        """Convert audio to SenseVoice features with query embeddings"""
        try:
            # Convert to float32 and normalize
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0

            # Extract features using frontend
            speech_features = self.frontend.get_features(audio_data)

            # Limit to reasonable sequence length
            max_frames = self.config['max_frames']
            if speech_features.shape[0] > max_frames:
                speech_features = speech_features[:max_frames, :]

            # Add language and text normalization queries
            language_id = LANGUAGES.get(language, 0)  # Default to auto
            language_query = self.embedding[[[language_id]]]

            # 14 means with itn, 15 means without itn
            text_norm_query = self.embedding[[[14 if use_itn else 15]]]
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
            return None