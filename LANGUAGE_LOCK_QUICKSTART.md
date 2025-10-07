# 🔒 Language Lock Quick Reference

## TL;DR

**Problem**: `LANGUAGE=auto` causes wobble (inconsistent language switching)  
**Solution**: Auto-lock to detected language after 10 second warmup  
**Result**: Consistent transcriptions, no language wobble  
**Cost**: Zero (uses existing model output)

## Quick Start

### Default Configuration (Recommended)
```yaml
environment:
  - LANGUAGE=auto  # Start with auto-detection
  - ENABLE_LANGUAGE_LOCK=true  # Enable auto-lock
  # Other defaults are fine
```

**What happens**:
1. 0-10s: Auto-detects language from speech
2. 10s: Analyzes most common language
3. 10s+: Locks to detected language, prevents wobble

### Example Output
```
🌍 Language detection warmup started
📝 Hello there [English]
📝 Good morning [English]
📝 How are you [English]
🔒 Language LOCKED to 'en' (confidence: 100%, samples: 3/3)
📝 Nice to meet you  ← No more wobble!
📝 What's your name  ← Consistent English!
```

## Configuration Options

| Variable | Default | When to Change |
|----------|---------|----------------|
| `ENABLE_LANGUAGE_LOCK` | `true` | Set `false` for true multi-lingual |
| `LANGUAGE_LOCK_WARMUP_S` | `10.0` | Lower for faster lock, higher for more confidence |
| `LANGUAGE_LOCK_MIN_SAMPLES` | `3` | Increase for more samples before lock |
| `LANGUAGE_LOCK_CONFIDENCE` | `0.6` | Increase for stricter lock (60% → 80%) |

## Common Scenarios

### 1. Fast Lock (Impatient)
```yaml
- LANGUAGE_LOCK_WARMUP_S=5.0
- LANGUAGE_LOCK_MIN_SAMPLES=2
```
Locks in ~5 seconds

### 2. Careful Lock (Cautious)
```yaml
- LANGUAGE_LOCK_WARMUP_S=20.0
- LANGUAGE_LOCK_MIN_SAMPLES=5
- LANGUAGE_LOCK_CONFIDENCE=0.8
```
Locks in ~20 seconds with 80% confidence

### 3. Disable Lock (True Multi-lingual)
```yaml
- ENABLE_LANGUAGE_LOCK=false
```
Stays in auto mode forever

### 4. Fixed Language (No Auto)
```yaml
- LANGUAGE=en  # Or zh, ja, ko, yue
```
No lock needed - already fixed

## Benefits

✅ **No wobble** - Consistent language after warmup  
✅ **Better accuracy** - Model knows expected language  
✅ **Consistent spelling** - Same words always spelled same way  
✅ **Zero overhead** - Uses existing model output  
✅ **Automatic** - No manual intervention needed  

## Full Documentation

📖 **[LANGUAGE_LOCK.md](LANGUAGE_LOCK.md)** - Complete guide with examples and troubleshooting
