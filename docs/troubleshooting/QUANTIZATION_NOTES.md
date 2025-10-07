# RKNN Quantization and Accuracy Notes

## Current Configuration
- **Model**: SenseVoice-RKNN (RK3588 NPU)
- **Quantization**: FP16 (not quantized to INT8)
- **SPEECH_SCALE**: 1/4 (reduced from 1/2 for better FP16 stability)

## Observed Issues
When testing with "this is test 2", the system produced variations:
- "This is De2."
- "This is test2."
- "This is thattu."
- "I that's too.."

## Root Cause Analysis

### FP16 Limitations
1. **Precision**: ~3-4 decimal digits vs FP32's ~7 digits
2. **Range**: Can cause overflow/underflow in activation functions
3. **Acoustic similarity**: Words like "test" and "De" have similar acoustic patterns that FP16 may not distinguish well

### NPU-Specific Considerations
1. **Hardware approximations**: RK3588 NPU may use fast approximations for:
   - Exponential functions (softmax)
   - Logarithms
   - Division operations
2. **Memory bandwidth**: FP16 uses less memory but requires careful scaling

## Solutions Attempted

### 1. SPEECH_SCALE Adjustment (CURRENT)
```python
SPEECH_SCALE = 1/4  # Previously 1/2
```
- **Purpose**: Prevent FP16 overflow in model activations
- **Trade-off**: May reduce dynamic range of features
- **Test**: Try speaking clearly and check if accuracy improves

### 2. INT8 Quantization (ALTERNATIVE)
To enable INT8 quantization (may actually improve accuracy with proper calibration):

```python
# In convert_rknn.py, change:
QUANTIZE = True  # Currently False
DATASET = "dataset.txt"  # Need to create calibration dataset
```

**Steps to try INT8:**
1. Create calibration dataset with diverse audio samples
2. Rebuild RKNN model with quantization enabled
3. Test accuracy - INT8 with good calibration often beats poorly-tuned FP16

## Recommendations

### Short Term
1. ✅ **SPEECH_SCALE reduced to 1/4** - Test and see if accuracy improves
2. Speak more clearly and slowly
3. Ensure good microphone positioning (6-12 inches)

### Medium Term
1. Create calibration dataset with diverse English speech samples
2. Test INT8 quantization vs FP16
3. Compare accuracy metrics

### Long Term
1. Consider using original ONNX model with CPU inference for accuracy comparison
2. Fine-tune model on your specific acoustic environment
3. Experiment with hybrid CPU/NPU inference (CPU for attention, NPU for features)

## Expected Accuracy
- **FP16 RKNN**: ~85-90% WER (Word Error Rate) compared to FP32
- **INT8 RKNN (well-calibrated)**: ~90-95% WER compared to FP32
- **FP32 ONNX CPU**: Baseline 100%

## Testing Protocol
To measure improvement after SPEECH_SCALE adjustment:

```bash
# Test with clear, distinct phrases
./setup.sh start
# Say: "This is test number two"
# Say: "The quick brown fox"
# Say: "One two three four five"
```

Look for:
- Fewer word substitutions
- Better handling of similar-sounding words
- More consistent transcriptions on repeated phrases

## References
- [RKNN FP16 Known Issues](https://github.com/rockchip-linux/rknn-toolkit2/blob/master/doc/02_Rockchip_RKNPU_User_Guide_RKNN_SDK_V1.6.0_EN.pdf)
- SenseVoice RKNN README: Known issue with FP16 overflow
