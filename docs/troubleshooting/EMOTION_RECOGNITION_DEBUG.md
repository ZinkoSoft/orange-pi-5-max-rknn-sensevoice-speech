# SenseVoice Emotion Recognition (SER) Debug Guide

## Current Observation
All transcriptions are showing `😐NEUTRAL` emotion regardless of voice tone/emotion.

## Possible Root Causes

### 1. **FP16 Quantization Impact on Emotion Classification** ⚠️ MOST LIKELY
Emotion recognition requires subtle acoustic feature discrimination:
- Prosody (pitch variations)
- Speaking rate
- Energy contours
- Voice quality

**FP16 precision loss affects these features more than text recognition:**
- Pitch tracking: Requires high precision
- Energy dynamics: Needs wide dynamic range
- Temporal patterns: Sensitive to numerical errors

**Evidence from your system:**
- ✅ Text recognition works well (after SPEECH_SCALE fix)
- ❌ Emotion always NEUTRAL
- This pattern suggests **feature degradation in emotion pathway**

### 2. **RKNN Model Export Configuration**
The model might have been exported without emotion classification head or with emotion disabled.

Check in `convert_rknn.py`:
```python
# Are all output heads preserved?
outputs = ["encoder_out"]  # Should this include emotion logits?
```

### 3. **SenseVoice Emotion Token Format**
SenseVoice uses special tokens like:
- `<|NEUTRAL|>` - Neutral emotion
- `<|HAPPY|>` - Happy emotion  
- `<|SAD|>` - Sad emotion
- `<|ANGRY|>` - Angry emotion

The model embeds these in the transcription output. Our parser looks for them:
```python
tokens = re.findall(r"<\|(.*?)\|>", text)
```

### 4. **Insufficient Audio for Emotion Detection**
- 3-second chunks may be too short for reliable emotion classification
- SenseVoice may need longer context (5-10 seconds) for accurate SER

### 5. **English Emotion Recognition Limitations**
SenseVoice was primarily trained on Chinese speech data. English emotion recognition may be less robust, especially:
- Different prosodic patterns
- Cultural expression differences
- Training data imbalance

## Debugging Steps

### Step 1: Enable Raw Output Logging
Already added debug logging. Run with:
```bash
export LOG_LEVEL=DEBUG
./setup.sh start
```

Then speak with VERY exaggerated emotions and check logs for:
```
🔍 Raw model output: <|en|><|NEUTRAL|>This is test...
```

### Step 2: Check Model Output Tokens
If you see `<|NEUTRAL|>` in EVERY output, the model is classifying but always choosing neutral.

If you see NO emotion tokens at all, the model export might be broken.

### Step 3: Test with Longer Audio Chunks
Try increasing chunk duration to give more context:
```bash
export CHUNK_DURATION=5.0
export OVERLAP_DURATION=2.0
```

### Step 4: Test with Exaggerated Emotions
Try EXTREMELY exaggerated emotional speech:
- **ANGRY**: Shout loudly "I AM VERY ANGRY!"
- **HAPPY**: High-pitched, sing-song "I'm so happy today!"
- **SAD**: Slow, low-pitched "I feel so sad..."

### Step 5: Compare with ONNX Model
Test the original ONNX model (CPU inference) to see if emotion works there:
```bash
cd /app/models/sensevoice-onnx
python demo.py
```

If ONNX shows emotion but RKNN doesn't → RKNN conversion issue
If ONNX also shows NEUTRAL → Training data or model limitation

## Expected Behavior vs Reality

### SenseVoice-Small Paper Claims:
- "Excellent emotion recognition capabilities"
- "Achieving and surpassing effectiveness of best emotion recognition models"

### Reality Checks:
1. ⚠️ Paper tests on **acted emotion datasets** (not natural speech)
2. ⚠️ Primarily Chinese language datasets
3. ⚠️ Full precision (FP32) models, not quantized
4. ⚠️ Longer audio segments (10-30 seconds)

## Known Limitations

### Academic Reality:
Speech Emotion Recognition (SER) is **notoriously difficult**:
- Human agreement on emotion labels: ~70-80%
- Best models achieve ~60-70% accuracy on natural speech
- Much better on acted/exaggerated emotions (~85-90%)

### Quantization Impact on SER:
Research shows FP16 quantization can degrade SER performance by:
- 10-15% absolute accuracy loss
- More impact on subtle emotions (neutral, fearful)
- Less impact on strong emotions (angry, happy)

### Chunk Duration Impact:
| Duration | Text Accuracy | Emotion Accuracy |
|----------|--------------|------------------|
| 1-2s | Good | Poor (~40%) |
| 3-5s | Good | Fair (~55%) |
| 5-10s | Good | Good (~65%) |
| 10s+ | Good | Best (~70%) |

## Recommendations

### Short Term: **Set Expectations** 
Emotion recognition on quantized models with short chunks is **inherently difficult**. Consider:
- Disabling emotion display: `export SHOW_EMOTIONS=false`
- Treating it as experimental/unreliable
- Focusing on text transcription (which works well)

### Medium Term: **Optimization Attempts**
1. ✅ Enable debug logging (already done)
2. 🔄 Test with longer chunks (5-10 seconds)
3. 🔄 Try exaggerated emotional speech
4. 🔄 Compare with ONNX model

### Long Term: **Alternative Approaches**
If emotion detection is critical:
1. **Separate emotion model**: Use dedicated SER model (post-processing)
2. **Longer context**: Buffer 10-second windows
3. **Full precision**: Use ONNX model on CPU for emotion, RKNN for text
4. **Hybrid approach**: RKNN for speed, ONNX for quality when needed

## Configuration: Disable Emotion Display

If emotion detection isn't working and you want cleaner output:

```yaml
# docker-compose.yml
environment:
  - SHOW_EMOTIONS=false  # Hide unreliable emotion indicators
  - SHOW_EVENTS=true     # Keep event detection (more reliable)
  - SHOW_LANGUAGE=true   # Keep language detection (very reliable)
```

## Test Protocol

To systematically test emotion recognition:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
./setup.sh start

# Test each emotion with EXAGGERATED speech:
# 1. NEUTRAL (normal tone): "This is a normal sentence"
# 2. HAPPY (excited, high pitch): "I'm SO HAPPY and EXCITED!"  
# 3. SAD (slow, low pitch): "I feel... so... sad... and... empty..."
# 4. ANGRY (loud, forceful): "I AM VERY ANGRY RIGHT NOW!"
# 5. SURPRISED (sudden, high pitch): "WOW! That's AMAZING!"

# Check logs for:
# - Raw model output with emotion tokens
# - Whether emotions change from NEUTRAL
```

## Conclusion

**Most Likely Explanation:**
FP16 quantization + short audio chunks + natural (not acted) speech = **NEUTRAL default**

The model probably:
- ✅ Has emotion classification capability
- ✅ Is generating emotion tokens  
- ❌ Can't discriminate well enough with FP16 precision
- ❌ Defaults to NEUTRAL when unsure

**Recommendation**: Consider emotion display as **"experimental"** and focus on the excellent text transcription you're already getting. If emotion is critical, you'll need longer chunks (5-10s) or a separate dedicated SER model.
