# 🎭 SenseVoice Rich Metadata Features

## Overview

SenseVoice is not just an ASR (Automatic Speech Recognition) model—it's a multi-modal speech understanding system with built-in capabilities for:

- **🗣️ ASR**: Automatic Speech Recognition (transcription)
- **🌍 LID**: Language Identification (auto-detect language)
- **😊 SER**: Speech Emotion Recognition (detect emotions)
- **🎵 AED**: Audio Event Detection (detect background sounds)

This implementation now fully exploits **all four capabilities** to provide rich, contextual transcriptions.

---

## 🌟 Features

### 1. Language Identification (LID)

**What it does**: Automatically detects which language is being spoken in real-time.

**Supported Languages**:
- 🇨🇳 Chinese (zh)
- 🇬🇧 English (en)
- 🇯🇵 Japanese (ja)
- 🇰🇷 Korean (ko)
- 🇭🇰 Cantonese (yue)

**Example Output**:
```
TRANSCRIPT: Hello, how are you? [English]
TRANSCRIPT: こんにちは [Japanese]
TRANSCRIPT: 你好吗 [Chinese]
```

**Use Cases**:
- Multi-lingual environments
- Language learning applications
- Verify expected language is being spoken
- Automatic language routing

---

### 2. Speech Emotion Recognition (SER)

**What it does**: Detects the emotional tone of the speaker's voice.

**Detected Emotions**:
- 😊 HAPPY - Joyful, positive speech
- 😢 SAD - Sorrowful, melancholic speech
- 😠 ANGRY - Frustrated, aggressive speech
- 😐 NEUTRAL - Calm, emotionless speech
- 😨 FEARFUL - Anxious, scared speech
- 🤢 DISGUSTED - Repulsed speech
- 😲 SURPRISED - Shocked, unexpected speech

**Example Output**:
```
TRANSCRIPT: 😊 I'm so happy to see you!
TRANSCRIPT: 😢 I miss you so much
TRANSCRIPT: 😠 This is unacceptable!
```

**Use Cases**:
- Customer service quality monitoring
- Mental health applications
- Interactive voice assistants
- Meeting sentiment analysis
- Call center analytics

---

### 3. Audio Event Detection (AED)

**What it does**: Detects non-speech audio events in the audio stream.

**Detected Events**:
- 🎵 BGM - Background music
- 👏 Applause - Clapping
- 😄 Laughter - Laughing sounds
- 😭 Crying - Crying sounds
- 🤧 Sneeze - Sneezing
- 🤒 Cough - Coughing
- 💨 Breath - Breathing sounds
- 💬 Speech - Normal speech (default)

**Example Output**:
```
TRANSCRIPT: 🎵 [music playing in background] Hello there
TRANSCRIPT: 👏 That was amazing! [followed by applause]
TRANSCRIPT: 🤒 *cough* Excuse me
```

**Use Cases**:
- Filter out music/noise from transcriptions
- Detect audience reactions (applause, laughter)
- Health monitoring (cough detection)
- Environmental audio analysis
- Smart filtering for clean transcriptions

---

## 🛠️ Configuration

### Environment Variables

Add these to your `docker-compose.yml` or export before running:

```yaml
environment:
  # Display Options
  - SHOW_EMOTIONS=true      # Show emotion emojis (😊😢😠)
  - SHOW_EVENTS=true        # Show event emojis (🎵👏😄)
  - SHOW_LANGUAGE=true      # Show detected language tags
  
  # Filtering Options
  - FILTER_BGM=false        # Skip transcriptions when BGM detected
  - FILTER_EVENTS=          # Comma-separated events to filter
                           # Example: "BGM,Applause,Cough"
```

### Configuration Examples

#### Example 1: Clean Transcriptions Only
**Skip background music and coughing**:
```yaml
environment:
  - FILTER_BGM=true
  - FILTER_EVENTS=Cough,Sneeze,Breath
  - SHOW_EMOTIONS=true
  - SHOW_EVENTS=false
```

#### Example 2: Full Rich Output
**Show everything**:
```yaml
environment:
  - SHOW_EMOTIONS=true
  - SHOW_EVENTS=true
  - SHOW_LANGUAGE=true
  - FILTER_BGM=false
  - FILTER_EVENTS=
```

#### Example 3: Customer Service Mode
**Emotion tracking without events**:
```yaml
environment:
  - SHOW_EMOTIONS=true
  - SHOW_EVENTS=false
  - SHOW_LANGUAGE=false
  - FILTER_BGM=true
  - FILTER_EVENTS=BGM,Applause,Laughter
```

#### Example 4: Multi-lingual Conference
**Focus on language detection**:
```yaml
environment:
  - SHOW_EMOTIONS=false
  - SHOW_EVENTS=false
  - SHOW_LANGUAGE=true
  - FILTER_BGM=true
```

---

## 📡 WebSocket Output Format

The WebSocket server now broadcasts rich metadata alongside transcriptions:

```json
{
  "type": "transcription",
  "text": "Hello, how are you?",
  "language": "English",
  "emotion": "HAPPY",
  "audio_events": [],
  "has_itn": true,
  "raw_text": "<|en|><|HAPPY|><|withitn|>Hello, how are you?",
  "confidence": "HIGH",
  "timestamp": "2025-10-07T10:30:45.123456",
  "source": "npu-sensevoice"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Clean transcription text (metadata removed) |
| `language` | string | Detected language name (e.g., "English") |
| `emotion` | string | Detected emotion (e.g., "HAPPY", "SAD") |
| `audio_events` | array | List of detected audio events (e.g., ["BGM", "Applause"]) |
| `has_itn` | boolean | Whether inverse text normalization was applied |
| `raw_text` | string | Original text with metadata tokens |
| `confidence` | string | Confidence level (always "HIGH" for now) |
| `timestamp` | string | ISO 8601 timestamp |
| `source` | string | Always "npu-sensevoice" |

---

## 🎯 Use Case Examples

### Use Case 1: Customer Support Analytics

**Goal**: Track customer emotions during support calls.

**Configuration**:
```yaml
- SHOW_EMOTIONS=true
- SHOW_EVENTS=false
- FILTER_BGM=true
- FILTER_EVENTS=BGM,Cough,Sneeze
```

**Example Output**:
```
TRANSCRIPT: 😠 This product doesn't work!
TRANSCRIPT: 😢 I've been waiting for two weeks
TRANSCRIPT: 😊 Thank you for your help!
```

**Analytics**: Count emotion frequencies to gauge customer satisfaction.

---

### Use Case 2: Podcast/Video Transcription

**Goal**: Clean transcriptions without background noise or music.

**Configuration**:
```yaml
- SHOW_EMOTIONS=false
- SHOW_EVENTS=false
- FILTER_BGM=true
- FILTER_EVENTS=BGM,Applause,Laughter,Cough
```

**Result**: Only clean speech transcriptions, no interruptions.

---

### Use Case 3: Multi-lingual Meeting

**Goal**: Track which language each speaker uses.

**Configuration**:
```yaml
- LANGUAGE=auto
- SHOW_LANGUAGE=true
- SHOW_EMOTIONS=false
- SHOW_EVENTS=false
```

**Example Output**:
```
TRANSCRIPT: Welcome everyone to the meeting [English]
TRANSCRIPT: 大家好 [Chinese]
TRANSCRIPT: Bonjour à tous [English]  # May detect as English if not trained on French
```

---

### Use Case 4: Health Monitoring

**Goal**: Detect coughing frequency in a room.

**Configuration**:
```yaml
- SHOW_EVENTS=true
- FILTER_EVENTS=  # Don't filter anything
```

**Example Output**:
```
TRANSCRIPT: 🤒 I'm feeling okay
TRANSCRIPT: 🤒 *cough*
TRANSCRIPT: 🤒 Maybe I should rest
```

**Analytics**: Count cough events over time.

---

## 🔧 Technical Details

### How It Works

1. **Input Processing**: Audio features are extracted and combined with task-specific query embeddings:
   - Language query embedding (for LID)
   - Event + Emotion query embeddings (for SER + AED)
   - Text normalization query (for ITN)

2. **Model Inference**: The SenseVoice model processes all queries simultaneously, outputting:
   - Token probabilities (for transcription)
   - Special tokens like `<|en|>`, `<|HAPPY|>`, `<|BGM|>`, etc.

3. **Output Parsing**: Our decoder extracts and interprets these special tokens:
   ```python
   # Example raw output from model:
   "<|en|><|HAPPY|><|withitn|>Hello, how are you?"
   
   # Parsed result:
   {
     'text': 'Hello, how are you?',
     'language': 'English',
     'emotion': 'HAPPY',
     'audio_events': [],
     'has_itn': True
   }
   ```

4. **Filtering**: Optional filtering based on detected events/emotions.

5. **Display**: Rich formatted output with emojis and metadata.

---

## 📊 Performance Impact

**Good News**: Extracting metadata has **ZERO performance overhead**!

- The model already computes all this information
- We were previously throwing it away by stripping metadata tokens
- Now we just parse what's already there
- No additional inference time required

**Benefits**:
- Smarter filtering (skip BGM = fewer wasted transcriptions)
- Better accuracy (language validation)
- Richer context (emotions + events)
- Same ~25ms inference time

---

## 🚀 Quick Start

### 1. Enable All Features
```bash
cd /path/to/orange-pi-5-max-rknn-sensevoice-speech

# Edit docker-compose.yml to enable features
# (already configured with defaults)

./setup.sh start
```

### 2. Test Emotion Detection
Speak with different emotions:
- Happy/excited voice: Should detect 😊 HAPPY
- Sad/slow voice: Should detect 😢 SAD
- Angry/loud voice: Should detect 😠 ANGRY

### 3. Test Event Detection
Play background music while speaking - should see 🎵 BGM tag.

### 4. Test Language Detection
```yaml
# Set language to auto in docker-compose.yml
- LANGUAGE=auto
```

Speak different languages and watch the language tags switch!

---

## 🐛 Troubleshooting

### Issue: Not seeing emotion/event tags

**Solution**: Check that model output includes metadata tokens:
```bash
# In container, check logs
docker-compose logs -f sensevoice-npu | grep "raw_text"
```

If `raw_text` field is empty or has no `<|...|>` tokens, the model may not be generating them.

### Issue: Too many filtered transcriptions

**Solution**: Reduce filtering aggressiveness:
```yaml
- FILTER_BGM=false
- FILTER_EVENTS=  # Empty = no filtering
```

### Issue: Wrong language detected

**Solution**: 
- For consistent single-language use, set explicit language instead of `auto`
- The model was trained on 5 languages, so others may be misdetected

---

## 📚 References

- [SenseVoice GitHub](https://github.com/FunAudioLLM/SenseVoice)
- [SenseVoice Paper](https://github.com/FunAudioLLM/SenseVoice) (see README for benchmarks)
- [FunASR Framework](https://github.com/modelscope/FunASR)

---

## 🎉 Summary

You're now using **100% of SenseVoice's capabilities** instead of just ASR!

**Before**: Just transcription text  
**Now**: Transcription + Language + Emotion + Audio Events

This makes your transcription system:
- ✅ More accurate (filter noise/music)
- ✅ More robust (multi-lingual support)
- ✅ More contextual (emotional tone)
- ✅ More intelligent (event-aware)

All with **zero performance overhead**! 🚀
