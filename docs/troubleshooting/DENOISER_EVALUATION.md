# NPU Denoiser Evaluation for SenseVoice Pipeline

## Proposal
Add an NPU-based denoiser (DTLN or DeepFilterNet) before ASR to improve robustness in noisy environments.

## Current System Performance
✅ **Already Working Well:**
- Adaptive noise floor tracking
- Multi-metric VAD (RMS + ZCR + Spectral Entropy)
- SPEECH_SCALE optimization for FP16 stability
- Good accuracy on clean speech: "This is test number two" → Perfect transcription

## Trade-off Analysis

### Pros of Adding NPU Denoiser
✅ Better performance in **extremely noisy** environments (>20dB SNR improvement possible)
✅ Improved far-field microphone performance
✅ NPU acceleration keeps it real-time
✅ Can help with stationary noise (fans, HVAC, traffic)

### Cons of Adding NPU Denoiser
❌ **Perceptual denoisers can hurt ASR accuracy** (see HN discussion)
❌ Adds 10-40ms latency per chunk
❌ Doubles model complexity (2 RKNN models to manage)
❌ NPU core allocation complexity (memory bandwidth contention)
❌ Denoisers trained for human listening may distort formants/pitch that ASR needs
❌ Requires careful tuning to avoid over-suppression
❌ May introduce artifacts that confuse SenseVoice's emotion/event detection

## Performance Impact Estimates

### Latency
| Stage | Current | With Denoiser |
|-------|---------|---------------|
| Audio Capture | ~3ms | ~3ms |
| **Denoiser** | **0ms** | **+15-40ms** |
| Feature Extract | ~5ms | ~5ms |
| NPU Inference | ~50ms | ~50ms |
| Decoding | ~2ms | ~2ms |
| **Total** | **~60ms** | **~75-100ms** |

### Memory
- Current: ~1.1GB (SenseVoice RKNN)
- With Denoiser: ~1.3-1.5GB (+ denoiser model)

### NPU Utilization
```
Current:
[NPU Core 0] ████████ SenseVoice (100%)
[NPU Core 1] -------- Idle
[NPU Core 2] -------- Idle

With Denoiser:
[NPU Core 0] ████████ Denoiser (100%)
[NPU Core 1] ████████ SenseVoice (100%)
[NPU Core 2] -------- Idle or shared memory bandwidth
```

## Alternative Approaches (Recommended First)

### 1. **CPU-Based Spectral Subtraction** ⭐ BEST FIRST TRY
- Latency: <1ms
- Complexity: Low
- Already have FFT in VAD code
- No new dependencies

```python
def apply_spectral_subtraction(audio_chunk, noise_profile, alpha=1.5):
    """Lightweight frequency-domain noise reduction"""
    fft = np.fft.rfft(audio_chunk)
    magnitude = np.abs(fft)
    phase = np.angle(fft)
    
    # Subtract noise profile
    clean_magnitude = np.maximum(magnitude - alpha * noise_profile, 0.1 * magnitude)
    
    clean_fft = clean_magnitude * np.exp(1j * phase)
    return np.fft.irfft(clean_fft, len(audio_chunk))
```

### 2. **Enhanced Adaptive Noise Floor**
- Use your existing calibration system
- Track noise profile per frequency band
- Already implemented and working!

### 3. **SoX Integration** (If needed for extreme cases)
```bash
# Preprocess with lightweight CPU denoising
sox input.wav output.wav noisered noise.prof 0.15
```

### 4. **Microphone-Level Noise Cancellation**
- AIRHUG microphone may have built-in noise cancellation
- Check device settings first
- Hardware solution = best solution

## Testing Protocol (Before Adding Denoiser)

### Step 1: Measure Current Performance in Target Environment
```bash
# Test in various noise conditions
# Record: clean, moderate noise (10dB SNR), heavy noise (0dB SNR)
# Measure WER (Word Error Rate) for each
```

### Step 2: Identify Failure Cases
- What types of noise cause problems? (stationary vs non-stationary)
- Is it microphone distance? (far-field vs near-field)
- Is it specific acoustic conditions? (echo, reverberation)

### Step 3: Try Lightweight Solutions First
1. Adjust VAD thresholds
2. Increase noise calibration time
3. Try spectral subtraction
4. Optimize microphone placement

### Step 4: Only Then Consider NPU Denoiser
- If WER > 30% in target environment
- If lightweight solutions fail
- If latency budget allows +40ms

## Models to Consider (If Proceeding)

### DTLN (Dual-signal Transformation LSTM Network)
- **Pros**: Real-time, small model (~2MB), proven ONNX export
- **Cons**: Trained for perceptual quality, may distort ASR features
- **Conversion**: ✅ ONNX → RKNN straightforward
- **Latency**: ~15ms on NPU

### DeepFilterNet
- **Pros**: Higher quality, more recent (2022)
- **Cons**: Larger model (~15MB), more complex, higher latency
- **Conversion**: ⚠️ ONNX export requires work
- **Latency**: ~30-40ms on NPU

### RNNoise (Fork for ASR)
- **Pros**: Specifically tuned to preserve ASR features
- **Cons**: Harder to find ONNX versions, older architecture
- **Conversion**: ⚠️ May need manual ONNX export
- **Latency**: ~10ms on NPU

## Recommendation

### Phase 1: **DO NOT ADD YET** ⚠️
Your current system is working well. The key issues were:
1. ✅ FP16 precision (FIXED with SPEECH_SCALE)
2. ✅ Decoding errors (FIXED with proper type conversion)

### Phase 2: **Measure & Test**
1. Test in your actual deployment environment
2. Measure WER in different noise conditions
3. Identify if noise is actually the bottleneck

### Phase 3: **Try Lightweight First**
1. Implement spectral subtraction (already have FFT)
2. Tune VAD thresholds for your environment
3. Optimize microphone positioning

### Phase 4: **Consider NPU Denoiser Only If:**
- WER > 30% in production environment
- Lightweight solutions fail
- Latency budget allows it
- You can find an **ASR-optimized** denoiser model

## Implementation Plan (If Needed)

### 1. Create Lightweight Toggle
```yaml
# docker-compose.yml
environment:
  - USE_DENOISER=false  # Off by default
  - DENOISER_TYPE=spectral  # spectral|dtln|deepfilternet
  - DENOISER_STRENGTH=0.15  # 0.0-1.0
```

### 2. Pipeline Architecture
```
Audio Input → [Optional: Denoiser] → VAD → Feature Extraction → SenseVoice → Output
                     ↓
              Easy to disable for testing
```

### 3. A/B Testing
- Run with/without denoiser
- Compare WER, latency, user experience
- Make data-driven decision

## References
- [HN Discussion on ASR Denoisers](https://news.ycombinator.com/item?id=36221534)
- [DTLN Paper](https://arxiv.org/abs/2005.07551)
- [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)
- [SenseVoice Architecture](https://github.com/FunAudioLLM/SenseVoice)

## Conclusion

**Wait and measure before adding complexity.** Your system is performing well after the SPEECH_SCALE fix. If you do need denoising:

1. ⭐ Try CPU spectral subtraction first (minimal risk)
2. 🤔 Consider NPU denoiser only if proven necessary
3. ⚠️ Be aware of ASR-vs-perceptual quality trade-offs
4. 📊 Always A/B test before committing

The best denoiser is often **no denoiser** + good microphone placement + adaptive VAD. 🎯
