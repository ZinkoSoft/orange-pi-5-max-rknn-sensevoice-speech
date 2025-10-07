# 🎯 Quick Reference: Rich Metadata Features

## TL;DR - What You Get

Your SenseVoice system now uses **100% of its capabilities** instead of just ASR:

| Feature | What It Does | Example |
|---------|--------------|---------|
| 🌍 **LID** | Auto-detect language | `Hello [English]` |
| 😊 **SER** | Detect emotions | `😊 I'm happy!` |
| 🎵 **AED** | Detect audio events | `🎵 Hello [with music]` |
| 🚫 **Filter** | Skip noise/music | Auto-skip BGM transcriptions |

**Performance**: Zero overhead (uses existing model output)

---

## Quick Start

### 1. Enable All Features (Default)
```bash
./setup.sh start
./setup.sh logs
```

Everything is enabled by default! Just speak and watch for:
- Emotion emojis: 😊😢😠
- Event emojis: 🎵👏😄
- Language tags: [English], [Chinese], etc.

### 2. Filter Background Music
Edit `docker-compose.yml`:
```yaml
- FILTER_BGM=true
- FILTER_EVENTS=BGM,Applause,Cough
```

Then restart:
```bash
./setup.sh restart
```

---

## Configuration Presets

### Preset 1: Clean Transcription (Podcasts/Videos)
```yaml
- FILTER_BGM=true
- FILTER_EVENTS=BGM,Applause,Laughter,Cough
- SHOW_EMOTIONS=false
- SHOW_EVENTS=false
```

### Preset 2: Customer Service Monitoring
```yaml
- SHOW_EMOTIONS=true
- SHOW_EVENTS=false
- FILTER_BGM=true
- FILTER_EVENTS=BGM
```

### Preset 3: Multi-lingual Meeting
```yaml
- LANGUAGE=auto
- SHOW_LANGUAGE=true
- SHOW_EMOTIONS=false
- SHOW_EVENTS=false
```

### Preset 4: Everything On (Default)
```yaml
- SHOW_EMOTIONS=true
- SHOW_EVENTS=true
- SHOW_LANGUAGE=true
- FILTER_BGM=false
- FILTER_EVENTS=
```

---

## All Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOW_EMOTIONS` | `true` | Display emotion emojis (😊😢😠) |
| `SHOW_EVENTS` | `true` | Display event emojis (🎵👏😄) |
| `SHOW_LANGUAGE` | `true` | Show language tags ([English]) |
| `FILTER_BGM` | `false` | Skip transcriptions with music |
| `FILTER_EVENTS` | `` | Skip specific events (comma-separated) |

---

## Example Output

### Before (Old System)
```
TRANSCRIPT: Hello world
TRANSCRIPT: Hello world
TRANSCRIPT: Hello world
```

### After (New System)
```
TRANSCRIPT: 😊 Hello world [English]
🚫 Filtered event: BGM
TRANSCRIPT: 😢 I miss you [Chinese]
TRANSCRIPT: 👏 Great job! [English]
```

---

## WebSocket API

Clients receive rich JSON:

```json
{
  "type": "transcription",
  "text": "Hello world",
  "language": "English",
  "emotion": "HAPPY",
  "audio_events": ["Speech"],
  "timestamp": "2025-10-07T10:30:45.123456"
}
```

---

## Testing

### Test Emotions
Speak with different emotions:
- **Happy/excited** → 😊 HAPPY
- **Sad/slow** → 😢 SAD  
- **Angry/loud** → 😠 ANGRY

### Test Events
Play background music → 🎵 BGM detected

### Test Languages
```yaml
- LANGUAGE=auto
```
Speak different languages → See language tags switch

---

## Documentation

- 📖 **[SENSEVOICE_FEATURES.md](../features/SENSEVOICE_FEATURES.md)** - Complete guide (470+ lines)
- 📋 **[RICH_METADATA_CHANGES.md](RICH_METADATA_CHANGES.md)** - Implementation summary
- 🚀 **[README.md](../../README.md)** - Main documentation

---

## Supported Tags

### Emotions (SER)
😊 HAPPY | 😢 SAD | 😠 ANGRY | 😐 NEUTRAL | 😨 FEARFUL | 🤢 DISGUSTED | 😲 SURPRISED

### Events (AED)
🎵 BGM | 👏 Applause | 😄 Laughter | 😭 Crying | 🤧 Sneeze | 🤒 Cough | 💨 Breath | 💬 Speech

### Languages (LID)
Chinese | English | Japanese | Korean | Cantonese

---

## Benefits

✅ **More Accurate** - Filter out music/noise automatically  
✅ **More Robust** - Multi-lingual support with auto-detection  
✅ **More Contextual** - See the emotional tone  
✅ **More Intelligent** - Event-aware transcription  
✅ **Zero Overhead** - No performance cost  

---

## Need Help?

- **Full guide**: [SENSEVOICE_FEATURES.md](../features/SENSEVOICE_FEATURES.md)
- **Changes**: [RICH_METADATA_CHANGES.md](RICH_METADATA_CHANGES.md)
- **Troubleshooting**: [README.md](README.md#-troubleshooting)
