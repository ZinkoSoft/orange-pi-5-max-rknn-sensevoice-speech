#!/bin/bash
#
# 🏥 SenseVoice Health Check Script
# =================================
# Monitors container health and NPU functionality
#

set -euo pipefail

# Configuration
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/app/models}"
HEALTH_CHECK_TIMEOUT=30

# Logging functions
log_info() {
    echo "[HEALTH] [$(date '+%H:%M:%S')] $*"
}

log_error() {
    echo "[HEALTH] [$(date '+%H:%M:%S')] ERROR: $*"
}

# Health check functions
check_npu_device() {
    if [[ ! -c /dev/rknpu ]]; then
        log_error "NPU device not accessible"
        return 1
    fi
    return 0
}

check_rknn_library() {
    if [[ ! -f /usr/lib/librknnrt.so ]]; then
        log_error "RKNN runtime library not found"
        return 1
    fi
    return 0
}

check_model_files() {
    local rknn_model="$MODEL_CACHE_DIR/sensevoice-rknn/sense-voice-encoder.rknn"
    
    if [[ ! -f "$rknn_model" ]]; then
        log_error "RKNN model file not found: $rknn_model"
        return 1
    fi
    
    # Check file size (should be ~485MB)
    local size=$(stat -c%s "$rknn_model" 2>/dev/null || echo "0")
    local min_size=$((400 * 1024 * 1024))  # 400MB minimum
    
    if [[ $size -lt $min_size ]]; then
        log_error "RKNN model file too small: $(($size / 1024 / 1024))MB"
        return 1
    fi
    
    return 0
}

check_python_imports() {
    timeout $HEALTH_CHECK_TIMEOUT python3 -c "
import sys
try:
    import numpy
    import librosa
    import pyaudio
    from rknnlite.api import RKNNLite
    print('[HEALTH] Python imports successful')
except ImportError as e:
    print(f'[HEALTH] Import error: {e}')
    sys.exit(1)
" || return 1
    
    return 0
}

check_npu_inference() {
    log_info "Testing NPU inference capability..."
    
    timeout $HEALTH_CHECK_TIMEOUT python3 -c "
import sys
import numpy as np
from rknnlite.api import RKNNLite

try:
    rknn = RKNNLite()
    
    # Load model
    model_path = '$MODEL_CACHE_DIR/sensevoice-rknn/sense-voice-encoder.rknn'
    ret = rknn.load_rknn(model_path)
    if ret != 0:
        print(f'[HEALTH] Failed to load model: {ret}')
        sys.exit(1)
    
    # Initialize runtime
    ret = rknn.init_runtime()
    if ret != 0:
        print(f'[HEALTH] Failed to initialize runtime: {ret}')
        sys.exit(1)
    
    # Test inference with dummy data
    test_input = np.random.randn(1, 80, 3000).astype(np.float32)
    outputs = rknn.inference(inputs=[test_input])
    
    if outputs is None or len(outputs) == 0:
        print('[HEALTH] NPU inference returned no outputs')
        sys.exit(1)
    
    rknn.release()
    print('[HEALTH] NPU inference test successful')
    
except Exception as e:
    print(f'[HEALTH] NPU test failed: {e}')
    sys.exit(1)
" || return 1
    
    return 0
}

check_audio_system() {
    # Check if audio devices exist
    if [[ ! -d /dev/snd ]]; then
        log_info "Audio devices not mounted (non-critical)"
        return 0
    fi
    
    # Test PyAudio initialization
    timeout $HEALTH_CHECK_TIMEOUT python3 -c "
import pyaudio
try:
    audio = pyaudio.PyAudio()
    device_count = audio.get_device_count()
    audio.terminate()
    print(f'[HEALTH] Audio system OK - {device_count} devices')
except Exception as e:
    print(f'[HEALTH] Audio system warning: {e}')
" || {
        log_info "Audio system check failed (non-critical)"
        return 0
    }
    
    return 0
}

check_disk_space() {
    # Check available disk space
    local available=$(df /app | tail -1 | awk '{print $4}')
    local min_space=1048576  # 1GB in KB
    
    if [[ $available -lt $min_space ]]; then
        log_error "Low disk space: $(($available / 1024))MB available"
        return 1
    fi
    
    return 0
}

check_log_directory() {
    if [[ ! -d /app/logs ]] || [[ ! -w /app/logs ]]; then
        log_error "Log directory not writable"
        return 1
    fi
    return 0
}

# Main health check
main_health_check() {
    local checks_passed=0
    local checks_total=0
    
    log_info "Starting comprehensive health check..."
    
    # Critical checks
    local critical_checks=(
        "NPU Device:check_npu_device"
        "RKNN Library:check_rknn_library"
        "Model Files:check_model_files"
        "Python Imports:check_python_imports"
        "Disk Space:check_disk_space"
        "Log Directory:check_log_directory"
    )
    
    # Non-critical checks
    local optional_checks=(
        "Audio System:check_audio_system"
    )
    
    # Run critical checks
    for check in "${critical_checks[@]}"; do
        local name="${check%:*}"
        local func="${check#*:}"
        
        ((checks_total++))
        log_info "Checking: $name"
        
        if $func; then
            log_info "✅ $name: PASS"
            ((checks_passed++))
        else
            log_error "❌ $name: FAIL"
        fi
    done
    
    # Run optional checks
    for check in "${optional_checks[@]}"; do
        local name="${check%:*}"
        local func="${check#*:}"
        
        log_info "Checking: $name"
        
        if $func; then
            log_info "✅ $name: PASS"
        else
            log_info "⚠️ $name: WARNING (non-critical)"
        fi
    done
    
    # NPU inference test (most important)
    log_info "Checking: NPU Inference"
    ((checks_total++))
    
    if check_npu_inference; then
        log_info "✅ NPU Inference: PASS"
        ((checks_passed++))
    else
        log_error "❌ NPU Inference: FAIL"
    fi
    
    # Health check summary
    log_info "Health Check Summary: $checks_passed/$checks_total critical checks passed"
    
    if [[ $checks_passed -eq $checks_total ]]; then
        log_info "🎉 All health checks passed - container is healthy!"
        return 0
    else
        log_error "🚨 Health check failed - container may not function properly"
        return 1
    fi
}

# Quick health check (for Docker HEALTHCHECK)  
quick_health_check() {
    # Minimal checks for Docker healthcheck
    check_npu_device && \
    check_rknn_library && \
    check_python_imports && \
    log_info "Quick health check passed" || {
        log_error "Quick health check failed"
        return 1
    }
}

# Command dispatcher
case "${1:-quick}" in
    "full")
        main_health_check
        ;;
    "quick")
        quick_health_check
        ;;
    "npu")
        check_npu_inference
        ;;
    "device")
        check_npu_device && check_rknn_library && log_info "NPU device check passed"
        ;;
    *)
        log_error "Usage: $0 [full|quick|npu|device]"
        exit 1
        ;;
esac