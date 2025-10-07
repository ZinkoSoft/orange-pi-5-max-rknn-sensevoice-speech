# 🔒 Language Auto-Lock Feature

## Overview

When using `LANGUAGE=auto`, SenseVoice can detect multiple languages dynamically. However, this can cause "language wobble" where the model switches between languages incorrectly, leading to inconsistent spellings and transcription errors.

**Language Auto-Lock** solves this by:
1. Starting with `LANGUAGE=auto` for initial detection
2. Collecting language detections during a "warmup period" (default: 10 seconds)
3. Locking to the most consistently detected language
4. Preventing language wobble for the rest of the session

## Why This Matters

### Problem: Language Wobble
```
TRANSCRIPT: Hello world [English]
TRANSCRIPT: Helo wurld [Chinese]  ← Misinterpreted as Chinese!
TRANSCRIPT: Hell world [English]
```

### Solution: Auto-Lock After Warmup
```
TRANSCRIPT: Hello world [English]
TRANSCRIPT: Hello there [English]
TRANSCRIPT: Good morning [English]
🔒 Language LOCKED to 'en' (confidence: 100%, samples: 3/3)
TRANSCRIPT: Hello again [English]  ← Consistent!
TRANSCRIPT: How are you [English]  ← No more wobble!
```

## How It Works

### Phase 1: Warmup (0-10 seconds)
- Model runs with `LANGUAGE=auto`
- System collects detected languages from each transcription
- No locking yet - allows initial detection

### Phase 2: Analysis (~10 seconds)
- System analyzes collected language samples
- Calculates confidence: `most_common_count / total_samples`
- Example: 8 English + 2 noise = 80% confidence

### Phase 3: Lock (10+ seconds)
- If confidence ≥ threshold (default 60%), lock to that language
- All future transcriptions use the locked language
- Prevents wobble and improves consistency

## Configuration

### Environment Variables

Add to `docker-compose.yml`:

```yaml
environment:
  # Must start with auto for lock to work
  - LANGUAGE=auto
  
  # Language lock settings
  - ENABLE_LANGUAGE_LOCK=true        # Enable auto-lock feature
  - LANGUAGE_LOCK_WARMUP_S=10.0      # Warmup duration (seconds)
  - LANGUAGE_LOCK_MIN_SAMPLES=3      # Minimum successful transcriptions
  - LANGUAGE_LOCK_CONFIDENCE=0.6     # Minimum confidence to lock (60%)
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_LANGUAGE_LOCK` | `true` | Enable language auto-lock |
| `LANGUAGE_LOCK_WARMUP_S` | `10.0` | Seconds to collect samples before locking |
| `LANGUAGE_LOCK_MIN_SAMPLES` | `3` | Minimum transcriptions needed to lock |
| `LANGUAGE_LOCK_CONFIDENCE` | `0.6` | Minimum % of samples in same language (0-1) |

### When Lock Happens

Lock triggers when **ALL** conditions met:
1. ✅ Warmup time elapsed (`LANGUAGE_LOCK_WARMUP_S` seconds)
2. ✅ Minimum samples collected (`LANGUAGE_LOCK_MIN_SAMPLES` transcriptions)
3. ✅ Confidence threshold met (e.g., 60% of samples are same language)

## Use Cases

### Use Case 1: English Office (Recommended)
**Scenario**: English-speaking office with occasional foreign words/names.

**Configuration**:
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=true
- LANGUAGE_LOCK_WARMUP_S=10.0
- LANGUAGE_LOCK_MIN_SAMPLES=3
- LANGUAGE_LOCK_CONFIDENCE=0.6
```

**Result**: Locks to English after 10 seconds, foreign names spelled consistently using English phonetics.

---

### Use Case 2: Fast Lock (Impatient Users)
**Scenario**: You know the language will be consistent, want faster lock.

**Configuration**:
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=true
- LANGUAGE_LOCK_WARMUP_S=5.0        # Faster!
- LANGUAGE_LOCK_MIN_SAMPLES=2       # Fewer samples
- LANGUAGE_LOCK_CONFIDENCE=0.7      # Higher confidence
```

**Result**: Locks within 5 seconds if 70%+ samples are same language.

---

### Use Case 3: Conservative Lock (Cautious)
**Scenario**: Mixed-language environment, want to be sure before locking.

**Configuration**:
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=true
- LANGUAGE_LOCK_WARMUP_S=20.0       # Longer observation
- LANGUAGE_LOCK_MIN_SAMPLES=5       # More samples
- LANGUAGE_LOCK_CONFIDENCE=0.8      # Higher confidence
```

**Result**: Locks only after 20 seconds with 80%+ consistency.

---

### Use Case 4: True Multi-lingual (Disable Lock)
**Scenario**: Genuinely switching between languages constantly (e.g., bilingual conversation).

**Configuration**:
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=false        # Disable!
```

**Result**: Stays in `auto` mode forever, switches languages dynamically.

---

### Use Case 5: Fixed Language (No Lock Needed)
**Scenario**: You already know the language, no detection needed.

**Configuration**:
```yaml
- LANGUAGE=en                        # Or zh, ja, ko, yue
# Lock settings ignored when not using 'auto'
```

**Result**: Always uses specified language, no warmup or detection.

## Example Logs

### Successful Lock
```
🌍 Language detection warmup started
📝 Hello there [English]
📝 Good morning [English]
📝 How are you [English]
🔒 Language LOCKED to 'en' (confidence: 100.0%, samples: 3/3)
📝 Nice to meet you
📝 What's your name
```

### Inconclusive Detection (Stays in Auto)
```
🌍 Language detection warmup started
📝 Hello [English]
📝 你好 [Chinese]
📝 こんにちは [Japanese]
📝 안녕하세요 [Korean]
⚠️ Language detection inconclusive after warmup (best: English at 25.0%), remaining in auto mode
📝 Hello again [English]
```

### Already Locked (Not Auto)
```
# No warmup - already configured to English
📝 Hello world
📝 Good morning
```

## Benefits

### ✅ Consistency
- No more spelling variations ("hello" vs "helo")
- Predictable transcription format
- Better duplicate detection (same spelling = easier to match)

### ✅ Performance
- Slightly faster inference (locked language = no LID overhead)
- Better decoding accuracy (model knows expected language)
- Reduced confusion on ambiguous words

### ✅ User Experience
- Predictable output format
- Fewer errors from language switching
- Clear indication when lock happens

## Technical Details

### Language Detection Process

1. **Input**: Audio features + language embedding
2. **Model Output**: Tokens including `<|en|>`, `<|zh|>`, etc.
3. **Parsing**: Extract language tag from output
4. **Tracking**: Store detected language in list
5. **Analysis**: Count most common after warmup
6. **Lock**: Update `current_language` to detected language

### Language Code Mapping

| Detected Name | Code | Used For Embedding |
|---------------|------|--------------------|
| English | `en` | `LANGUAGES['en'] = 4` |
| Chinese | `zh` | `LANGUAGES['zh'] = 3` |
| Japanese | `ja` | `LANGUAGES['ja'] = 11` |
| Korean | `ko` | `LANGUAGES['ko'] = 12` |
| Cantonese | `yue` | `LANGUAGES['yue'] = 7` |

### Zero Performance Overhead

Language locking uses **existing model output**:
- Model already computes language (multi-task head)
- We just parse and count the tags
- No extra inference or processing
- Same ~25ms inference time

## Troubleshooting

### Issue: Not locking after warmup

**Check logs for**:
```
⚠️ Language detection inconclusive after warmup
```

**Solutions**:
1. Lower `LANGUAGE_LOCK_CONFIDENCE` (e.g., 0.5 = 50%)
2. Increase `LANGUAGE_LOCK_WARMUP_S` (collect more samples)
3. Speak more clearly during warmup
4. Ensure audio quality is good

---

### Issue: Locked to wrong language

**Cause**: Warmup period had noisy/unclear audio.

**Solutions**:
1. Restart container to retry warmup
2. Set fixed `LANGUAGE=en` instead of auto
3. Increase `LANGUAGE_LOCK_MIN_SAMPLES` for more samples
4. Increase `LANGUAGE_LOCK_CONFIDENCE` for stricter lock

---

### Issue: Want to switch language mid-session

**Solution**: Restart the container. Language lock is per-session only.

```bash
./setup.sh restart
```

---

### Issue: Always detecting wrong language during warmup

**Cause**: Background noise, accent, or audio quality.

**Solutions**:
1. Set fixed language: `LANGUAGE=en`
2. Disable auto-lock: `ENABLE_LANGUAGE_LOCK=false`
3. Improve microphone quality
4. Reduce background noise

## Performance Impact

| Aspect | Impact |
|--------|--------|
| Inference Time | ✅ None (uses existing output) |
| Memory | ✅ Negligible (~100 bytes for tracking) |
| CPU | ✅ None (simple list operations) |
| Accuracy | ✅ **Improved** (no language wobble) |
| Consistency | ✅ **Much better** (locked language) |

## Recommendations

### For Most Users (Default)
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=true
- LANGUAGE_LOCK_WARMUP_S=10.0
- LANGUAGE_LOCK_MIN_SAMPLES=3
- LANGUAGE_LOCK_CONFIDENCE=0.6
```

### For Known Single Language
```yaml
- LANGUAGE=en  # Or zh, ja, ko, yue
# No lock needed
```

### For True Multi-lingual
```yaml
- LANGUAGE=auto
- ENABLE_LANGUAGE_LOCK=false
```

## Summary

**Problem**: Language auto-detection causes wobble and inconsistency.

**Solution**: Auto-lock to most common language after warmup.

**Benefits**:
- ✅ Consistent spelling and transcription
- ✅ No language wobble after initial detection
- ✅ Better accuracy and duplicate detection
- ✅ Zero performance overhead
- ✅ Automatic - no manual intervention needed

**When to use**: When you expect consistent language but don't know which one initially.

**When NOT to use**: True bilingual conversations that constantly switch languages.
