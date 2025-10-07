#!/bin/bash
# Quick configuration tester for NPU optimization features

echo "========================================"
echo "NPU Optimization Configuration Helper"
echo "========================================"
echo ""

# Function to show current config
show_config() {
    echo "Current Configuration:"
    echo "-------------------"
    echo "SIMILARITY_THRESHOLD=${SIMILARITY_THRESHOLD:-0.85 (default)}"
    echo "ENABLE_VAD=${ENABLE_VAD:-true (default)}"
    echo "VAD_ZCR_MIN=${VAD_ZCR_MIN:-0.02 (default)}"
    echo "VAD_ZCR_MAX=${VAD_ZCR_MAX:-0.35 (default)}"
    echo "VAD_ENTROPY_MAX=${VAD_ENTROPY_MAX:-0.85 (default)}"
    echo "ADAPTIVE_NOISE_FLOOR=${ADAPTIVE_NOISE_FLOOR:-true (default)}"
    echo "RMS_MARGIN=${RMS_MARGIN:-0.004 (default)}"
    echo "NOISE_CALIB_SECS=${NOISE_CALIB_SECS:-1.5 (default)}"
    echo "DUPLICATE_COOLDOWN_S=${DUPLICATE_COOLDOWN_S:-4.0 (default)}"
    echo ""
}

# Preset configurations
apply_preset() {
    case $1 in
        "default")
            echo "✅ Applying DEFAULT preset (balanced)"
            export SIMILARITY_THRESHOLD=0.85
            export ENABLE_VAD=true
            export VAD_MODE=accurate
            export VAD_ZCR_MIN=0.02
            export VAD_ZCR_MAX=0.35
            export VAD_ENTROPY_MAX=0.85
            export ADAPTIVE_NOISE_FLOOR=true
            export RMS_MARGIN=0.004
            export DUPLICATE_COOLDOWN_S=4.0
            ;;
        "noisy")
            echo "✅ Applying NOISY environment preset"
            export SIMILARITY_THRESHOLD=0.80
            export ENABLE_VAD=true
            export VAD_MODE=accurate
            export VAD_ZCR_MIN=0.02
            export VAD_ZCR_MAX=0.40
            export VAD_ENTROPY_MAX=0.90
            export ADAPTIVE_NOISE_FLOOR=true
            export RMS_MARGIN=0.008
            export DUPLICATE_COOLDOWN_S=3.0
            ;;
        "quiet")
            echo "✅ Applying QUIET environment preset"
            export SIMILARITY_THRESHOLD=0.90
            export ENABLE_VAD=true
            export VAD_MODE=accurate
            export VAD_ZCR_MIN=0.01
            export VAD_ZCR_MAX=0.35
            export VAD_ENTROPY_MAX=0.80
            export ADAPTIVE_NOISE_FLOOR=true
            export RMS_MARGIN=0.002
            export DUPLICATE_COOLDOWN_S=4.0
            ;;
        "simple")
            echo "✅ Applying SIMPLE mode (minimal processing)"
            export SIMILARITY_THRESHOLD=1.0
            export ENABLE_VAD=false
            export ADAPTIVE_NOISE_FLOOR=false
            export RMS_MARGIN=0.004
            export DUPLICATE_COOLDOWN_S=4.0
            ;;
        "aggressive")
            echo "✅ Applying AGGRESSIVE deduplication preset"
            export SIMILARITY_THRESHOLD=0.75
            export ENABLE_VAD=true
            export VAD_MODE=fast
            export VAD_ZCR_MIN=0.02
            export VAD_ZCR_MAX=0.35
            export VAD_ENTROPY_MAX=0.85
            export ADAPTIVE_NOISE_FLOOR=true
            export RMS_MARGIN=0.006
            export DUPLICATE_COOLDOWN_S=5.0
            ;;
        "fast")
            echo "✅ Applying FAST mode (low latency, optimized CPU usage)"
            export SIMILARITY_THRESHOLD=0.85
            export ENABLE_VAD=true
            export VAD_MODE=fast
            export VAD_ZCR_MIN=0.02
            export VAD_ZCR_MAX=0.35
            export ADAPTIVE_NOISE_FLOOR=true
            export RMS_MARGIN=0.004
            export DUPLICATE_COOLDOWN_S=4.0
            ;;
        *)
            echo "❌ Unknown preset: $1"
            echo "Available presets: default, noisy, quiet, simple, aggressive, fast"
            return 1
            ;;
    esac
}

# Show menu
if [ $# -eq 0 ]; then
    echo "Usage: $0 [preset]"
    echo ""
    echo "Available presets:"
    echo "  default     - Balanced settings (recommended starting point)"
    echo "  fast        - Low latency mode with optimized CPU VAD (< 0.5ms overhead)"
    echo "  noisy       - Optimized for noisy environments"
    echo "  quiet       - Optimized for quiet environments"
    echo "  simple      - Minimal processing, basic functionality"
    echo "  aggressive  - Maximum duplicate suppression"
    echo ""
    echo "Examples:"
    echo "  $0 default        # Use default settings"
    echo "  $0 noisy          # Configure for noisy environment"
    echo ""
    echo "To apply and run:"
    echo "  source $0 noisy && python3 src/live_transcription.py"
    echo ""
    show_config
    exit 0
fi

# Apply preset
apply_preset "$1"

if [ $? -eq 0 ]; then
    echo ""
    show_config
    echo "Configuration applied! Run your application now."
    echo ""
    echo "Suggested commands:"
    echo "  python3 src/live_transcription.py"
    echo "  # or with Docker:"
    echo "  docker-compose up"
fi
