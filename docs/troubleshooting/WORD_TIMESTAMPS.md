# Word-Level Timestamps for Chunk Merging

## Current State
The system uses:
- **CTC argmax decoding** → token IDs
- **Token-level confidences** → available (per-token probability)
- **NO timestamps** → not extracted from CTC alignment

## Problem
Without timestamps, we can't implement clean timeline-based merging:
```python
# Ideal approach (requires timestamps):
for word in new_chunk:
    if word.t_end <= global_last_time:
        skip  # already emitted
    elif word.t_start < global_last_time:
        # Overlap: keep higher confidence
        if word.confidence > prev_word.confidence:
            replace(prev_word, word)
    else:
        append(word)
```

## Why SenseVoice/RKNN Doesn't Have Timestamps

### CTC Model Architecture
SenseVoice uses **CTC (Connectionist Temporal Classification)**:
- Input: Mel spectrogram frames (171 frames = ~5.3 seconds audio)
- Output: Token logits per frame [vocab_size, num_frames]
- Decoding: Collapse repeated tokens + remove blanks → text

**CTC provides frame-level logits, not word boundaries.**

### Current Decoding
```python
# In transcription_decoder.py
logits = output_tensor[0]  # [vocab, T=171]
ids = np.argmax(logits, axis=0)  # [T] - token per frame
ids, confidences = unique_consecutive_with_confidence(ids, probs)
text = self.sp.DecodeIds(ids_list)  # SentencePiece tokens → text
```

**We lose timing information when collapsing consecutive tokens.**

## Solutions

### Option 1: CTC Forced Alignment (Feasible) ⭐

Extract timestamps by tracking which frames map to which tokens:

```python
def decode_with_timestamps(logits, probs, frame_duration_ms=31.25):
    """
    CTC decode with per-token timestamps.
    
    Args:
        logits: [vocab, T] - model output
        probs: [vocab, T] - softmax probabilities
        frame_duration_ms: Time per frame (171 frames / 5.3s = 31.25ms)
    
    Returns:
        List of (token_id, start_time_ms, end_time_ms, confidence)
    """
    ids = np.argmax(logits, axis=0)  # [T]
    tokens_with_timing = []
    
    i = 0
    while i < len(ids):
        token_id = ids[i]
        
        if token_id == blank_id:
            i += 1
            continue
        
        # Find span of this token
        start_frame = i
        max_conf = probs[token_id, i]
        
        while i < len(ids) and ids[i] == token_id:
            max_conf = max(max_conf, probs[token_id, i])
            i += 1
        
        end_frame = i
        
        # Convert frame indices to timestamps
        start_time_ms = start_frame * frame_duration_ms
        end_time_ms = end_frame * frame_duration_ms
        
        tokens_with_timing.append({
            'token_id': token_id,
            'start_ms': start_time_ms,
            'end_ms': end_time_ms,
            'confidence': float(max_conf)
        })
    
    return tokens_with_timing
```

### Option 2: Word-Level Alignment (More Complex)

SentencePiece tokens → words needs additional mapping:

```python
def tokens_to_words_with_timestamps(token_list, sp_model):
    """
    Convert SentencePiece tokens with timestamps to words.
    
    Challenges:
    - SentencePiece uses subword units (BPE)
    - "hello" might be ["▁hel", "lo"] with separate timestamps
    - Need to merge subwords into words
    """
    words_with_timing = []
    current_word = []
    current_start = None
    current_end = None
    current_confidences = []
    
    for token_info in token_list:
        token_id = token_info['token_id']
        token_text = sp_model.IdToPiece(token_id)
        
        # SentencePiece uses ▁ for word boundaries
        if token_text.startswith('▁'):
            # Start of new word
            if current_word:
                # Finalize previous word
                words_with_timing.append({
                    'word': ''.join(current_word).replace('▁', ''),
                    'start_ms': current_start,
                    'end_ms': current_end,
                    'confidence': np.mean(current_confidences)
                })
            
            # Start new word
            current_word = [token_text]
            current_start = token_info['start_ms']
            current_end = token_info['end_ms']
            current_confidences = [token_info['confidence']]
        else:
            # Continuation of current word
            current_word.append(token_text)
            current_end = token_info['end_ms']
            current_confidences.append(token_info['confidence'])
    
    # Finalize last word
    if current_word:
        words_with_timing.append({
            'word': ''.join(current_word).replace('▁', ''),
            'start_ms': current_start,
            'end_ms': current_end,
            'confidence': np.mean(current_confidences)
        })
    
    return words_with_timing
```

### Option 3: Timeline-Based Chunk Merging

With word timestamps, implement clean merging:

```python
class TimelineMerger:
    def __init__(self):
        self.global_timeline = []  # List of (word, start_ms, end_ms, conf)
        self.last_emit_time_ms = 0.0
    
    def merge_chunk(self, words_with_timing, chunk_offset_ms):
        """
        Merge new chunk into global timeline.
        
        Args:
            words_with_timing: List of {word, start_ms, end_ms, confidence}
            chunk_offset_ms: Global time offset for this chunk
        """
        new_words = []
        
        for word_info in words_with_timing:
            # Adjust to global timeline
            global_start = chunk_offset_ms + word_info['start_ms']
            global_end = chunk_offset_ms + word_info['end_ms']
            
            # Skip words already emitted
            if global_end <= self.last_emit_time_ms:
                continue
            
            # Handle overlap
            if global_start < self.last_emit_time_ms < global_end:
                # Word spans boundary - check if we should replace
                # Find overlapping word in timeline
                for i, prev_word in enumerate(reversed(self.global_timeline)):
                    if prev_word['end_ms'] > self.last_emit_time_ms:
                        # Compare confidences
                        if word_info['confidence'] > prev_word['confidence']:
                            # Replace with higher confidence version
                            self.global_timeline.pop(len(self.global_timeline) - 1 - i)
                            new_words.append({
                                'word': word_info['word'],
                                'start_ms': global_start,
                                'end_ms': global_end,
                                'confidence': word_info['confidence']
                            })
                        break
            else:
                # New word, no overlap
                new_words.append({
                    'word': word_info['word'],
                    'start_ms': global_start,
                    'end_ms': global_end,
                    'confidence': word_info['confidence']
                })
        
        # Update timeline and last emit time
        self.global_timeline.extend(new_words)
        if new_words:
            self.last_emit_time_ms = max(w['end_ms'] for w in new_words)
        
        return new_words
```

## Implementation Plan

### Phase 1: Add Token-Level Timestamps ✅ Easy
```python
# Modify decode_output() in transcription_decoder.py
def decode_output(self, output_tensor, audio_hash=None, chunk_start_time_ms=0):
    # ... existing code ...
    
    # NEW: Extract token timestamps
    tokens_with_timing = self._decode_with_timestamps(ids, probs, confidences)
    
    # NEW: Convert to words with timestamps
    words_with_timing = self._tokens_to_words(tokens_with_timing)
    
    return {
        'text': text_clean,
        'words': words_with_timing,  # NEW!
        'confidence': avg_confidence,
        # ... other metadata ...
    }
```

### Phase 2: Timeline-Based Merging 🔄 Medium
```python
# Modify live_transcription.py
class LiveTranscriber:
    def __init__(self):
        self.timeline_merger = TimelineMerger()
        self.chunk_counter = 0
        self.chunk_duration_ms = 3000  # 3 seconds
    
    def _process_audio_worker(self):
        # ... existing audio processing ...
        
        result = self.transcription_decoder.decode_output(
            npu_output, 
            audio_hash,
            chunk_start_time_ms=self.chunk_counter * self.chunk_duration_ms
        )
        
        if result and result.get('words'):
            # Merge using timeline
            new_words = self.timeline_merger.merge_chunk(
                result['words'],
                self.chunk_counter * self.chunk_duration_ms
            )
            
            if new_words:
                # Display only NEW words
                text = ' '.join(w['word'] for w in new_words)
                print(f"TRANSCRIPT: {text}")
        
        self.chunk_counter += 1
```

### Phase 3: Display Optimization ⚡ Easy
```python
# Only emit complete, confident words
def should_emit_word(word_info):
    return (
        word_info['confidence'] >= 0.5 and  # High confidence
        len(word_info['word']) >= 2 and      # Not fragments
        word_info['word'].isalpha()          # Real word
    )
```

## Pros & Cons

### Pros ✅
- **Clean merging**: No text heuristics
- **Monotonic output**: Words only added, never revised
- **Confidence-based**: Keep best version of overlapping words
- **Accurate timing**: Frame-level precision (~31ms)

### Cons ❌
- **Complexity**: More code to maintain
- **SentencePiece mapping**: Subword → word alignment tricky
- **Memory**: Store timeline (minimal: ~100 words = ~10KB)
- **Latency**: Small overhead for alignment (~2-5ms)

## Recommendation

### Implement Timeline-Based Merging! ⭐

**Why:**
1. Your observation is correct - current output is messy for display
2. CTC provides frame-level information we're not using
3. Timeline approach is cleaner than text heuristics
4. Enables future features (word highlighting, karaoke mode, etc.)

**Effort:**
- Phase 1 (timestamps): ~2-3 hours coding + testing
- Phase 2 (merging): ~3-4 hours coding + testing
- Phase 3 (display): ~1 hour

**Total: ~1 day of work for much cleaner output**

### Quick Win: Display Filter (Interim Solution)

While implementing timeline merging, add a simple filter:

```python
# In config.py
'min_display_words': 5,          # Only show chunks with 5+ words
'display_confidence_min': 0.55,  # Only show high-confidence chunks
```

This would reduce spam from:
```
"Once to part."
"Once upon a time, there was a small."
"On a time, there was a small lighthouse..."
```

To:
```
"Once upon a time, there was a small lighthouse that stood on the edge of rocky cliff."
"Every night, its golden light swept across the waves, guiding ships safely to shore."
```

**Would you like me to implement:**
1. Quick display filter (30 minutes) 🏃
2. Full timeline-based merging (1 day) 🚀
3. Both (filter first, then upgrade to timeline) ✅

Let me know!
