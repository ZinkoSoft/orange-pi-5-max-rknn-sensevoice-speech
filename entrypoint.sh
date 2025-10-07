#!/bin/bash
#
# 🚀 SenseVoice Container Entrypoint
# ==================================
# Manages model download, NPU initialization, and service startup
#

set -euo pipefail

# Configuration
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/app/models}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
COMMAND="${1:-live-transcription}"

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_warn() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $*"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*"
}

# System checks
check_npu_access() {
    log_info "🔍 Checking NPU device access..."
    
    # Check if renderD129 (actual NPU device) is available
    if [[ -c /dev/dri/renderD129 ]]; then
        log_info "✅ NPU device found at /dev/dri/renderD129"
        
        # Try to create symlink if it doesn't exist, but don't fail if we can't
        if [[ ! -e /dev/rknpu ]]; then
            log_info "📎 Attempting to create NPU device symlink..."
            if ln -sf /dev/dri/renderD129 /dev/rknpu 2>/dev/null; then
                log_info "✅ Created symlink /dev/rknpu -> /dev/dri/renderD129"
            else
                log_info "ℹ️ Using direct path /dev/dri/renderD129 (symlink creation failed)"
            fi
        fi
    elif [[ -c /dev/rknpu ]]; then
        log_info "✅ NPU device found at /dev/rknpu"
    else
        log_error "❌ NPU device not found"
        log_error "   Available devices in /dev/dri/:"
        ls -la /dev/dri/ 2>/dev/null || echo "   No DRI devices found"
        log_error "   Make sure container is run with: --privileged --device=/dev/dri"
        return 1
    fi
    
    if [[ ! -f /usr/lib/librknnrt.so ]]; then
        log_error "❌ RKNN runtime library not found: /usr/lib/librknnrt.so"
        log_error "   Make sure container is run with: -v /usr/lib/librknnrt.so:/usr/lib/librknnrt.so"
        return 1
    fi
    
    log_info "✅ NPU device and runtime library accessible"
    return 0
}

check_audio_access() {
    log_info "🔍 Checking audio device access..."
    
    if [[ ! -d /dev/snd ]]; then
        log_warn "⚠️ Audio devices not found in /dev/snd"
        log_warn "   Audio functionality may be limited"
        return 1
    fi
    
    # Test audio device listing
    if command -v arecord >/dev/null 2>&1; then
        log_info "🎤 Available audio devices:"
        arecord -l 2>/dev/null || log_warn "   No audio devices detected"
    fi
    
    log_info "✅ Audio access configured"
    return 0
}

# Model management
ensure_models_downloaded() {
    log_info "📥 Ensuring SenseVoice models are available..."
    
    # Run model download script
    if /app/scripts/download_models.sh check; then
        log_info "✅ Models are already cached and valid"
    else
        log_info "📥 Downloading models..."
        if /app/scripts/download_models.sh download; then
            log_info "✅ Model download completed successfully"
        else
            log_error "❌ Model download failed"
            return 1
        fi
    fi
    
    # Verify model paths
    local rknn_model="$MODEL_CACHE_DIR/sensevoice-rknn/sense-voice-encoder.rknn"
    if [[ ! -f "$rknn_model" ]]; then
        log_error "❌ RKNN model not found after download: $rknn_model"
        return 1
    fi
    
    log_info "✅ Models ready for inference"
    return 0
}

# Service startup functions
start_live_transcription() {
    log_info "🎙️ Starting live transcription service..."
    
    # Set model path
    export MODEL_PATH="$MODEL_CACHE_DIR/sensevoice-rknn/sense-voice-encoder.rknn"
    
    # Execute the live transcription script
    exec python3 /app/src/live_transcription.py
}

start_web_interface() {
    log_info "🌐 Starting web interface with live transcription..."
    
    # Set model path
    export MODEL_PATH="$MODEL_CACHE_DIR/sensevoice-rknn/sense-voice-encoder.rknn"
    
    # Start web server in background
    python3 /app/src/web_server.py --port 8080 --host 0.0.0.0 &
    WEB_SERVER_PID=$!
    log_info "✅ Web server started (PID: $WEB_SERVER_PID)"
    
    # Start live transcription in foreground
    python3 /app/src/live_transcription.py
}

start_model_test() {
    log_info "🧪 Starting model test..."
    
    # Simple model inference test
    python3 -c "
import sys
sys.path.append('/app/src')
from live_transcription import NPUSenseVoiceTranscriber
import numpy as np

try:
    transcriber = NPUSenseVoiceTranscriber()
    test_input = np.random.randn(1, 80, 3000).astype(np.float32)
    result = transcriber._npu_inference(test_input)
    
    if result is not None:
        print('✅ NPU inference test successful!')
        print(f'   Output shape: {result.shape}')
    else:
        print('❌ NPU inference test failed!')
        sys.exit(1)
        
    transcriber.cleanup()
    print('✅ Model test completed successfully!')
    
except Exception as e:
    print(f'❌ Model test failed: {e}')
    sys.exit(1)
"
}

start_health_check() {
    log_info "🏥 Running health check..."
    exec /app/healthcheck.sh
}

# Environment setup
setup_environment() {
    log_info "⚙️ Setting up environment..."
    
    # Create required directories
    mkdir -p /app/logs /app/cache "$MODEL_CACHE_DIR"
    
    # Set permissions
    chmod 755 /app/logs /app/cache "$MODEL_CACHE_DIR"
    
    # Export environment variables
    export PYTHONPATH="/app/src:${PYTHONPATH:-}"
    export MODEL_CACHE_DIR="$MODEL_CACHE_DIR"
    
    log_info "✅ Environment setup completed"
}

# Main startup sequence
startup_sequence() {
    log_info "🚀 SenseVoice Container Starting Up..."
    log_info "=" * 50
    log_info "Command: $COMMAND"
    log_info "Model Cache: $MODEL_CACHE_DIR"
    log_info "Log Level: $LOG_LEVEL"
    log_info "=" * 50
    
    # Setup environment
    setup_environment
    
    # System checks
    check_npu_access || {
        log_error "❌ NPU access check failed"
        exit 1
    }
    
    check_audio_access || {
        log_warn "⚠️ Audio access check failed (non-critical)"
    }
    
    # Ensure models are available
    ensure_models_downloaded || {
        log_error "❌ Model preparation failed"
        exit 1
    }
    
    log_info "✅ Startup sequence completed successfully"
}

# Command dispatcher
case "$COMMAND" in
    "live-transcription")
        startup_sequence
        start_live_transcription
        ;;
    "web-interface")
        startup_sequence
        start_web_interface
        ;;
    "test")
        startup_sequence
        start_model_test
        ;;
    "health")
        start_health_check
        ;;
    "download-models")
        setup_environment
        /app/scripts/download_models.sh download
        ;;
    "bash"|"shell")
        startup_sequence
        log_info "🐚 Starting interactive shell..."
        exec /bin/bash
        ;;
    *)
        log_error "❌ Unknown command: $COMMAND"
        log_info "Available commands:"
        log_info "  live-transcription : Start live transcription (default)"
        log_info "  web-interface     : Start web interface with live transcription"
        log_info "  test              : Run model inference test"
        log_info "  health            : Run health check"
        log_info "  download-models   : Download models only"
        log_info "  bash              : Interactive shell"
        exit 1
        ;;
esac