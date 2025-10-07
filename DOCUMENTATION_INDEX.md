# Documentation Index

Complete guide to all documentation files in this project.

## 🚀 Getting Started

### [QUICKSTART.md](QUICKSTART.md)
**5-minute guide to get up and running**
- Prerequisites check
- Installation steps
- Basic commands
- Quick troubleshooting

### [README.md](README.md)
**Main project documentation**
- Feature overview
- Complete setup guide
- Configuration reference
- Troubleshooting
- Performance benchmarks

## 🔧 Optimization & Performance

### [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)
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

### [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md)
**Quick reference of all changes**
- Files modified
- Configuration examples
- Before/after comparisons
- Rollback instructions
- Key metrics

## 🎤 Voice Activity Detection (VAD)

### [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md)
**Deep technical dive into VAD (highly detailed)**
- NPU vs CPU analysis
- Performance breakdown
- Optimization techniques
- Configuration options
- When to use each mode
- Technical algorithms
- Real NPU use cases

### [VAD_NPU_ANALYSIS.md](VAD_NPU_ANALYSIS.md)
**Why NPU VAD doesn't make sense (executive summary)**
- Quick answer to "Can we use NPU for VAD?"
- Performance comparison
- Trade-off analysis
- Bottom line recommendations

### [VAD_COMPARISON.md](VAD_COMPARISON.md)
**Visual comparisons and diagrams**
- Performance bar charts
- Pipeline diagrams
- Resource usage visualization
- Accuracy comparisons
- Power consumption graphs

## 📊 Technical Details

### [PIPELINE_DIAGRAM.md](PIPELINE_DIAGRAM.md)
**Visual processing pipeline overview**
- Before/after flowcharts
- Feature details
- Data flow diagrams
- Integration points
- Performance metrics

## 📖 Documentation Quick Reference

### By Purpose

**"I want to get started quickly"**
→ [QUICKSTART.md](QUICKSTART.md) → [README.md](README.md)

**"I want to optimize for my environment"**
→ [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) → `scripts/configure_optimization.sh`

**"I'm seeing duplicates"**
→ [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) (Duplicate Detection section)

**"I'm missing quiet speech"**
→ [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) (Tuning Guide - Quiet Environments)

**"Too much noise is being transcribed"**
→ [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) (Tuning Guide - Noisy Environments)

**"Should I use NPU for VAD?"**
→ [VAD_NPU_ANALYSIS.md](VAD_NPU_ANALYSIS.md) (TL;DR: No)

**"I want to understand VAD performance"**
→ [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md) → [VAD_COMPARISON.md](VAD_COMPARISON.md)

**"What changed in v2.0?"**
→ [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) → [README.md](README.md) (Changelog)

**"How does the pipeline work?"**
→ [PIPELINE_DIAGRAM.md](PIPELINE_DIAGRAM.md)

**"I need configuration reference"**
→ [README.md](README.md) (Configuration section) → [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)

### By Experience Level

**Beginner (just want it to work)**
1. [QUICKSTART.md](QUICKSTART.md)
2. [README.md](README.md)
3. Use default settings
4. Done!

**Intermediate (want to optimize)**
1. [README.md](README.md)
2. [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)
3. [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md)
4. Tune settings for your environment

**Advanced (want to understand everything)**
1. [README.md](README.md)
2. [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)
3. [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md)
4. [PIPELINE_DIAGRAM.md](PIPELINE_DIAGRAM.md)
5. [VAD_COMPARISON.md](VAD_COMPARISON.md)
6. Review source code in `src/`

**Expert (want to contribute/modify)**
1. All documentation above
2. Source code review (`src/`)
3. [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) for architecture
4. Review test results and benchmarks

### By Topic

#### Performance
- [README.md](README.md) - Performance Optimization section
- [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) - Performance Improvements
- [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md) - VAD Performance
- [VAD_COMPARISON.md](VAD_COMPARISON.md) - Benchmarks

#### Configuration
- [README.md](README.md) - Environment Variables
- [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) - Configuration Summary
- [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) - Configuration Examples
- `scripts/configure_optimization.sh` - Preset configurator

#### Troubleshooting
- [QUICKSTART.md](QUICKSTART.md) - Quick troubleshooting
- [README.md](README.md) - Comprehensive troubleshooting
- [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) - Troubleshooting section

#### Technical Details
- [PIPELINE_DIAGRAM.md](PIPELINE_DIAGRAM.md) - Architecture
- [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md) - Algorithms
- [VAD_COMPARISON.md](VAD_COMPARISON.md) - Visual explanations

#### Voice Activity Detection
- [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md) - Complete guide
- [VAD_NPU_ANALYSIS.md](VAD_NPU_ANALYSIS.md) - Summary
- [VAD_COMPARISON.md](VAD_COMPARISON.md) - Visual comparisons

## 📁 File Sizes (Approximate Reading Time)

| Document | Size | Reading Time | Level |
|----------|------|--------------|-------|
| [QUICKSTART.md](QUICKSTART.md) | 2 KB | 5 min | Beginner |
| [README.md](README.md) | 15 KB | 15 min | All |
| [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) | 3 KB | 5 min | Intermediate |
| [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md) | 18 KB | 25 min | Intermediate |
| [VAD_NPU_ANALYSIS.md](VAD_NPU_ANALYSIS.md) | 4 KB | 7 min | Intermediate |
| [VAD_OPTIMIZATION.md](VAD_OPTIMIZATION.md) | 30 KB | 45 min | Advanced |
| [VAD_COMPARISON.md](VAD_COMPARISON.md) | 12 KB | 15 min | Advanced |
| [PIPELINE_DIAGRAM.md](PIPELINE_DIAGRAM.md) | 10 KB | 15 min | Advanced |
| **Total** | **94 KB** | **~2.5 hours** | - |

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

## 🤝 Contributing to Documentation

If you find errors or have suggestions:
1. Open an issue describing the problem
2. Suggest improvements or corrections
3. Submit a pull request with updates

**Documentation quality is just as important as code quality!**

---

*Last updated: October 7, 2025*
*Total documentation: 8 files, ~94KB, 2.5 hours reading time*
