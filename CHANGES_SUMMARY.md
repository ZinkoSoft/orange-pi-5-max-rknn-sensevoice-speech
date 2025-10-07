# Summary of Changes - NPU & Accuracy Optimization

## Files Modified

### 1. `src/model_manager.py`
**Change**: NPU core usage optimization
- Changed from `NPU_CORE_0_1_2` (3 cores) to `NPU_CORE_0` (1 core)
- Reason: Sequential inference doesn't benefit from multiple cores
- Impact: Lower overhead, reduced power consumption

### 2. `src/transcription_decoder.py`
**Changes**: Enhanced duplicate detection
- Added `levenshtein_similarity()` function for fuzzy string matching
- Increased history window from 4 to 6 items
- Added audio chunk hash tracking (`_chunk_hashes`, `_hash_to_text`)
- Enhanced `decode_output()` with:
  - Audio hash deduplication check
  - Fuzzy similarity matching (configurable threshold)
  - Better duplicate suppression logic
- Added `add_audio_hash()` method for chunk tracking

### 3. `src/audio_processor.py`
**Changes**: Advanced Voice Activity Detection (VAD)
- Added configurable VAD parameters (ZCR min/max, entropy max)
- New methods:
  - `calculate_zero_crossing_rate()`: Detects speech characteristics
  - `calculate_spectral_entropy()`: Measures signal complexity
  - `is_speech_segment()`: Multi-feature VAD combining energy, ZCR, and entropy
- Returns detailed metrics for debugging

### 4. `src/live_transcription.py`
**Changes**: Integrated VAD and adaptive noise floor
- Added adaptive noise floor tracking variables
- Replaced simple RMS check with advanced VAD
- Adaptive noise floor updates every 50 non-speech chunks using median
- Added audio chunk fingerprinting (MD5 hash)
- Pass audio hash to decoder for deduplication
- Enhanced debug logging with VAD metrics

### 5. `src/config.py`
**Changes**: Added new configuration options
- New config keys:
  - `similarity_threshold`: 0.85 (fuzzy match threshold)
  - `enable_vad`: True (enable/disable VAD)
  - `vad_zcr_min`: 0.02 (minimum ZCR for speech)
  - `vad_zcr_max`: 0.35 (maximum ZCR for speech)
  - `vad_entropy_max`: 0.85 (maximum entropy for speech)
  - `adaptive_noise_floor`: True (enable adaptive updates)
- Added environment variable mappings for all new settings

### 6. `OPTIMIZATION_GUIDE.md` (NEW)
**Purpose**: Comprehensive documentation
- Detailed explanation of all improvements
- Configuration guide with examples
- Performance expectations and trade-offs
- Tuning guide for different environments
- Debugging tips and troubleshooting
- Technical details and algorithms

## Quick Test

After deploying these changes, you can test with:

```bash
# Build and run
docker-compose up --build

# Or if running directly
python3 src/live_transcription.py

# Monitor logs for VAD decisions
# Look for: ✅ Speech detected, Skip (VAD), 🔁 Suppress duplicate
```

## Expected Results

1. **Fewer Duplicates**: Should see significantly fewer repeated transcriptions
2. **Better Quiet Audio**: More accurate detection of soft speech
3. **Less Noise**: Fewer false transcriptions from background noise
4. **Cleaner Output**: Better quality transcription stream

## Configuration Examples

### Default (Recommended)
No changes needed - optimized defaults are set

### Noisy Environment
```bash
export VAD_ENTROPY_MAX=0.90
export RMS_MARGIN=0.008
export SIMILARITY_THRESHOLD=0.80
```

### Very Quiet Environment
```bash
export VAD_ZCR_MIN=0.01
export RMS_MARGIN=0.002
export SIMILARITY_THRESHOLD=0.90
```

### Disable Advanced Features (Simple Mode)
```bash
export ENABLE_VAD=false
export ADAPTIVE_NOISE_FLOOR=false
```

## Rollback Plan

If issues occur, you can easily rollback:

### Disable NPU Optimization
In `src/model_manager.py`, change back to:
```python
ret = self.rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0_1_2)
```

### Disable VAD
```bash
export ENABLE_VAD=false
```

### Disable Adaptive Noise Floor
```bash
export ADAPTIVE_NOISE_FLOOR=false
```

### Use Exact Match Only
```bash
export SIMILARITY_THRESHOLD=1.0
```

## Next Steps

1. Deploy changes
2. Monitor performance for 15-30 minutes
3. Check logs for duplicate suppression messages
4. Tune thresholds if needed based on your specific environment
5. Report back with results

## Key Metrics to Watch

- Number of "🔁 Suppress duplicate" messages (should increase)
- Number of "Skip (VAD)" vs "✅ Speech detected" (ratio should be reasonable)
- Quality of transcriptions during quiet speech
- False positives from background noise (should decrease)
