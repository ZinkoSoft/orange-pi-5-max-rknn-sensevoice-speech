# Documentation Index

Complete guide to all documentation files in this project.

## 🚀 Getting Started

### [QUICKSTART.md](getting-started/QUICKSTART.md)
**5-minute guide to get up and running**
- Prerequisites check
- Installation steps
- Basic commands
- Quick troubleshooting

### [README.md](../README.md)
**Main project documentation**
- Feature overview
- Complete setup guide
- Configuration reference
- Troubleshooting
- Performance benchmarks

## 🔧 Optimization & Performance

### [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md)
**Complete optimization reference (comprehensive)**
- NPU core usage optimization
- Duplicate detection with fuzzy matching
- Voice Activity Detection (VAD)
- Adaptive noise floor
- Audio chunk fingerprinting
- Configuration guide
- Tuning for different environments
- Performance expectations
- Troubleshooting tips

### [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md)
**Quick reference of all changes**
- Files modified
- Configuration examples
- Before/after comparisons
- Rollback instructions
- Key metrics

## 🏗️ Architecture & Design

### [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) 🔥 NEW!
**SOLID principles implementation guide**
- Refactoring overview and motivation
- New component architecture (5 new classes)
- Before/after code metrics (75% reduction in main class)
- SOLID principles implementation
- Component responsibilities and APIs
- Testing strategy
- Performance impact analysis (zero overhead)
- Migration guide for developers
- Benefits: maintainability, testability, reusability

## 🎤 Voice Activity Detection (VAD)

### [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md)
**Deep technical dive into VAD (highly detailed)**
- NPU vs CPU analysis
- Performance breakdown
- Optimization techniques
- Configuration options
- When to use each mode
- Technical algorithms
- Real NPU use cases

### [VAD_NPU_ANALYSIS.md](optimization/VAD_NPU_ANALYSIS.md)
**Why NPU VAD doesn't make sense (executive summary)**
- Quick answer to "Can we use NPU for VAD?"
- Performance comparison
- Trade-off analysis
- Bottom line recommendations

### [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md)
**Visual comparisons and diagrams**
- Performance bar charts
- Pipeline diagrams
- Resource usage visualization
- Accuracy comparisons
- Power consumption graphs

## 📊 Technical Details

### [PIPELINE_DIAGRAM.md](optimization/PIPELINE_DIAGRAM.md)
**Visual processing pipeline overview**
- Before/after flowcharts
- Feature details
- Data flow diagrams
- Integration points
- Performance metrics

## 🎭 Rich Metadata Features

### [SENSEVOICE_FEATURES.md](features/SENSEVOICE_FEATURES.md) 🆕
**Complete guide to SenseVoice's built-in capabilities**
- Language Identification (LID) - Auto-detect language
- Speech Emotion Recognition (SER) - Detect emotions
- Audio Event Detection (AED) - Detect background sounds
- Configuration examples
- Use case scenarios
- WebSocket output format
- Zero-overhead metadata extraction
- Filtering and display options

### [LANGUAGE_LOCK.md](features/LANGUAGE_LOCK.md) 🆕
**Language auto-lock feature guide**
- Why language wobble happens
- How auto-lock prevents inconsistency
- Configuration options
- Warmup period behavior
- Use case examples
- Troubleshooting tips
- Performance impact (zero overhead)

### [CONFIDENCE_STITCHING_QUICKSTART.md](features/CONFIDENCE_STITCHING_QUICKSTART.md) 🔥 NEW!
**Quick guide to confidence-gated chunk stitching**
- What is confidence-gated stitching
- How it improves boundary handling
- Quick enable instructions
- Configuration parameters
- Performance impact (negligible)
- Integration with existing features

### [CONFIDENCE_STITCHING.md](features/CONFIDENCE_STITCHING.md) 🔥 NEW!
**Complete technical guide to confidence-gated stitching**
- Problem analysis and solution
- Technical implementation details
- Confidence calculation methodology
- Boundary detection algorithms
- Tuning guide for different scenarios
- Performance benchmarks
- Best practices and troubleshooting

## � Debugging & Issues

### [TODAYS_FIXES.md](troubleshooting/TODAYS_FIXES.md) 🆕
**Summary of critical bugs fixed (October 7, 2025)**
- Text decoding error fix
- SPEECH_SCALE optimization for FP16
- Emotion recognition analysis
- Performance results
- Key takeaways

### [QUANTIZATION_NOTES.md](troubleshooting/QUANTIZATION_NOTES.md) 🆕
**FP16 quantization accuracy analysis**
- Current configuration
- Root cause analysis
- Solutions attempted
- Recommendations
- Testing protocol

### [EMOTION_RECOGNITION_DEBUG.md](troubleshooting/EMOTION_RECOGNITION_DEBUG.md) 🆕
**Emotion detection limitations and debugging**
- Why emotion recognition shows all NEUTRAL
- FP16 quantization impact on SER
- Debugging steps
- Expected vs actual behavior
- Recommendations

### [DENOISER_EVALUATION.md](troubleshooting/DENOISER_EVALUATION.md) 🆕
**NPU denoiser feasibility analysis**
- Trade-off analysis
- Performance impact estimates
- Alternative approaches
- Testing protocol
- Recommendations

## �📖 Documentation Quick Reference

### By Purpose

**"I want to get started quickly"**
→ [QUICKSTART.md](getting-started/QUICKSTART.md) → [README.md](../README.md)

**"I want to optimize for my environment"**
→ [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) → `scripts/configure_optimization.sh`

**"I'm seeing duplicates"**
→ [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) (Duplicate Detection section)

**"I'm missing quiet speech"**
→ [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) (Tuning Guide - Quiet Environments)

**"Too much noise is being transcribed"**
→ [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) (Tuning Guide - Noisy Environments)

**"Should I use NPU for VAD?"**
→ [VAD_NPU_ANALYSIS.md](optimization/VAD_NPU_ANALYSIS.md) (TL;DR: No)

**"How do I use emotion/language/event detection?"** 🆕
→ [SENSEVOICE_FEATURES.md](features/SENSEVOICE_FEATURES.md)

**"How do I filter out background music?"** 🆕
→ [SENSEVOICE_FEATURES.md](features/SENSEVOICE_FEATURES.md) (Configuration section)

**"What languages can it detect?"** 🆕
→ [SENSEVOICE_FEATURES.md](features/SENSEVOICE_FEATURES.md) (Language Identification section)

**"How do I prevent language wobble?"** 🆕
→ [LANGUAGE_LOCK.md](features/LANGUAGE_LOCK.md)

**"Language keeps switching incorrectly"** 🆕
→ [LANGUAGE_LOCK.md](features/LANGUAGE_LOCK.md) (Enable auto-lock feature)

**"I'm seeing garbled text at chunk boundaries"** 🔥 NEW!
→ [CONFIDENCE_STITCHING_QUICKSTART.md](features/CONFIDENCE_STITCHING_QUICKSTART.md)

**"How does confidence-gated stitching work?"** 🔥 NEW!
→ [CONFIDENCE_STITCHING.md](features/CONFIDENCE_STITCHING.md)

**"Why is emotion detection always NEUTRAL?"** 🆕
→ [EMOTION_RECOGNITION_DEBUG.md](troubleshooting/EMOTION_RECOGNITION_DEBUG.md)

**"What bugs were fixed today?"** 🆕
→ [TODAYS_FIXES.md](troubleshooting/TODAYS_FIXES.md)

**"Why is transcription accuracy poor?"** 🆕
→ [QUANTIZATION_NOTES.md](troubleshooting/QUANTIZATION_NOTES.md) → [TODAYS_FIXES.md](troubleshooting/TODAYS_FIXES.md)

**"Should I add an NPU denoiser?"** 🆕
→ [DENOISER_EVALUATION.md](troubleshooting/DENOISER_EVALUATION.md)

**"I want to understand VAD performance"**
→ [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md) → [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md)

**"What changed in v2.0?"**
→ [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md) → [README.md](../README.md) (Changelog)

**"How does the pipeline work?"**
→ [PIPELINE_DIAGRAM.md](optimization/PIPELINE_DIAGRAM.md)

**"Why was the code refactored?"** 🔥 NEW!
→ [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md)

**"How do I understand the new component structure?"** 🔥 NEW!
→ [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) (Component Overview section)

**"What are the SOLID principles?"** 🔥 NEW!
→ [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) (Benefits section)

**"How do I test individual components?"** 🔥 NEW!
→ [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) (Testing Strategy section)

**"I need configuration reference"**
→ [README.md](../README.md) (Configuration section) → [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md)

### By Experience Level

**Beginner (just want it to work)**
1. [QUICKSTART.md](getting-started/QUICKSTART.md)
2. [README.md](../README.md)
3. Use default settings
4. Done!

**Intermediate (want to optimize)**
1. [README.md](../README.md)
2. [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md)
3. [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md)
4. Tune settings for your environment

**Advanced (want to understand everything)**
1. [README.md](../README.md)
2. [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md)
3. [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md)
4. [PIPELINE_DIAGRAM.md](optimization/PIPELINE_DIAGRAM.md)
5. [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md)
6. Review source code in `src/`

**Expert (want to contribute/modify)**
1. All documentation above
2. Source code review (`src/`)
3. [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md) for architecture
4. Review test results and benchmarks

### By Topic

#### Performance
- [README.md](../README.md) - Performance Optimization section
- [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) - Performance Improvements
- [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md) - VAD Performance
- [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md) - Benchmarks

#### Configuration
- [README.md](../README.md) - Environment Variables
- [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) - Configuration Summary
- [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md) - Configuration Examples
- `scripts/configure_optimization.sh` - Preset configurator

#### Troubleshooting
- [QUICKSTART.md](getting-started/QUICKSTART.md) - Quick troubleshooting
- [README.md](../README.md) - Comprehensive troubleshooting
- [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) - Troubleshooting section

#### Technical Details
- [PIPELINE_DIAGRAM.md](optimization/PIPELINE_DIAGRAM.md) - Architecture
- [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md) - Algorithms
- [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md) - Visual explanations
- [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) - Code architecture

#### Voice Activity Detection
- [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md) - Complete guide
- [VAD_NPU_ANALYSIS.md](optimization/VAD_NPU_ANALYSIS.md) - Summary
- [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md) - Visual comparisons

#### Architecture & Code Design
- [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) - SOLID principles
- Component breakdown and responsibilities
- Testing strategies
- Migration guides

## 📁 File Sizes (Approximate Reading Time)

| Document | Size | Reading Time | Level |
|----------|------|--------------|-------|
| [QUICKSTART.md](getting-started/QUICKSTART.md) | 2 KB | 5 min | Beginner |
| [README.md](../README.md) | 15 KB | 15 min | All |
| [CHANGES_SUMMARY.md](optimization/CHANGES_SUMMARY.md) | 3 KB | 5 min | Intermediate |
| [OPTIMIZATION_GUIDE.md](optimization/OPTIMIZATION_GUIDE.md) | 18 KB | 25 min | Intermediate |
| [VAD_NPU_ANALYSIS.md](optimization/VAD_NPU_ANALYSIS.md) | 4 KB | 7 min | Intermediate |
| [VAD_OPTIMIZATION.md](optimization/VAD_OPTIMIZATION.md) | 30 KB | 45 min | Advanced |
| [VAD_COMPARISON.md](optimization/VAD_COMPARISON.md) | 12 KB | 15 min | Advanced |
| [PIPELINE_DIAGRAM.md](optimization/PIPELINE_DIAGRAM.md) | 10 KB | 15 min | Advanced |
| [SENSEVOICE_FEATURES.md](features/SENSEVOICE_FEATURES.md) | 12 KB | 15 min | Intermediate |
| [LANGUAGE_LOCK.md](features/LANGUAGE_LOCK.md) | 8 KB | 10 min | Intermediate |
| [CONFIDENCE_STITCHING_QUICKSTART.md](features/CONFIDENCE_STITCHING_QUICKSTART.md) | 3 KB | 5 min | Beginner |
| [CONFIDENCE_STITCHING.md](features/CONFIDENCE_STITCHING.md) | 15 KB | 20 min | Advanced |
| [TODAYS_FIXES.md](troubleshooting/TODAYS_FIXES.md) | 8 KB | 10 min | All |
| [QUANTIZATION_NOTES.md](troubleshooting/QUANTIZATION_NOTES.md) | 6 KB | 8 min | Advanced |
| [EMOTION_RECOGNITION_DEBUG.md](troubleshooting/EMOTION_RECOGNITION_DEBUG.md) | 10 KB | 12 min | Intermediate |
| [DENOISER_EVALUATION.md](troubleshooting/DENOISER_EVALUATION.md) | 12 KB | 15 min | Advanced |
| [ARCHITECTURE_REFACTORING.md](ARCHITECTURE_REFACTORING.md) | 20 KB | 25 min | Advanced |
| **Total** | **188 KB** | **~5 hours** | - |

## 🎯 Recommended Reading Paths

### Path 1: Quick User (15 minutes)
```
QUICKSTART.md → README.md (Quick Start section)
→ Start using default settings
→ Return to docs if needed
```

### Path 2: Optimizing User (45 minutes)
```
README.md (full read)
→ OPTIMIZATION_GUIDE.md
→ CHANGES_SUMMARY.md (for reference)
→ Configure and test
```

### Path 3: Deep Dive (2-3 hours)
```
README.md
→ OPTIMIZATION_GUIDE.md
→ VAD_OPTIMIZATION.md
→ PIPELINE_DIAGRAM.md
→ VAD_COMPARISON.md
→ Source code review
```

### Path 4: VAD Specialist (1 hour)
```
VAD_NPU_ANALYSIS.md (quick answer)
→ VAD_OPTIMIZATION.md (deep dive)
→ VAD_COMPARISON.md (visual understanding)
→ Configure VAD settings
```

### Path 5: Developer/Contributor (1.5 hours)
```
README.md
→ ARCHITECTURE_REFACTORING.md (code structure)
→ OPTIMIZATION_GUIDE.md (features)
→ Source code review in src/
→ Review new component classes
```

## 🔍 Search Tips

Use GitHub's search (press `/` in browser) or `grep` to find specific topics:

```bash
# Find all mentions of a configuration option
grep -r "SIMILARITY_THRESHOLD" *.md

# Find troubleshooting sections
grep -r "Troubleshooting" *.md

# Find performance metrics
grep -r "Improvement\|faster\|reduction" *.md
```

## 📝 Documentation Maintenance

All documentation is:
- ✅ Up to date as of October 7, 2025
- ✅ Tested on Orange Pi 5 Max with RK3588 NPU
- ✅ Reflects v2.0 optimization release
- ✅ Includes real performance benchmarks
- ✅ Includes v2.0 architecture refactoring details

## 🤝 Contributing to Documentation

If you find errors or have suggestions:
1. Open an issue describing the problem
2. Suggest improvements or corrections
3. Submit a pull request with updates

**Documentation quality is just as important as code quality!**

---

*Last updated: October 7, 2025*
*Total documentation: 17 files, ~188KB, 5 hours reading time*
