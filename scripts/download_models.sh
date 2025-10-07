#!/bin/bash
#
# 🚀 SenseVoice Model Download Script
# ===================================
# Downloads and caches SenseVoice RKNN models with integrity checking
#

set -euo pipefail

# Configuration
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/app/models}"
HF_CACHE_DIR="${HUGGINGFACE_HUB_CACHE:-/app/cache}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Model URLs and checksums
RKNN_REPO="happyme531/SenseVoiceSmall-RKNN2"
ONNX_REPO="FunAudioLLM/SenseVoiceSmall" 
RKNN_MODEL="sense-voice-encoder.rknn"
RKNN_SIZE_MB=485
ONNX_MODEL="sense-voice-encoder.onnx"
ONNX_SIZE_MB=937

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

# Check if model exists and is valid
check_model_integrity() {
    local model_path="$1"
    local expected_size_mb="$2"
    
    if [[ ! -f "$model_path" ]]; then
        log_info "Model not found: $model_path"
        return 1
    fi
    
    # Check file size
    local actual_size=$(stat -c%s "$model_path" 2>/dev/null || echo "0")
    local expected_size=$((expected_size_mb * 1024 * 1024))
    local size_diff=$((actual_size - expected_size))
    
    # Allow 10% variance in file size
    local tolerance=$((expected_size / 10))
    
    if [[ ${size_diff#-} -gt $tolerance ]]; then
        log_warn "Model size mismatch: expected ~${expected_size_mb}MB, got $((actual_size / 1024 / 1024))MB"
        return 1
    fi
    
    # Check if file is readable
    if [[ ! -r "$model_path" ]]; then
        log_error "Model file not readable: $model_path"
        return 1
    fi
    
    log_info "Model integrity check passed: $model_path"
    return 0
}

# Download model using git or huggingface-cli
download_model() {
    local repo="$1"
    local target_dir="$2"
    local model_name="$3"
    
    log_info "Downloading model from $repo..."
    
    # Create target directory
    mkdir -p "$target_dir"
    
    # Try multiple download methods
    local download_success=false
    
    # Method 1: Git clone (most reliable)
    if command -v git >/dev/null 2>&1; then
        log_info "Attempting git clone method..."
        if git clone "https://huggingface.co/$repo" "$target_dir" 2>/dev/null; then
            download_success=true
            log_info "Git clone successful"
        else
            log_warn "Git clone failed, trying alternative method..."
        fi
    fi
    
    # Method 2: Hugging Face CLI (if available)
    if [[ "$download_success" == "false" ]] && command -v huggingface-cli >/dev/null 2>&1; then
        log_info "Attempting huggingface-cli download..."
        if huggingface-cli download "$repo" --local-dir "$target_dir" 2>/dev/null; then
            download_success=true
            log_info "Hugging Face CLI download successful"
        else
            log_warn "Hugging Face CLI download failed..."
        fi
    fi
    
    # Method 3: Python script with requests (fallback)
    if [[ "$download_success" == "false" ]]; then
        log_info "Attempting Python download method..."
        python3 -c "
import os
import requests
from huggingface_hub import hf_hub_download
try:
    hf_hub_download(
        repo_id='$repo',
        filename='$model_name',
        local_dir='$target_dir',
        local_dir_use_symlinks=False
    )
    print('Python download successful')
except Exception as e:
    print(f'Python download failed: {e}')
    exit(1)
" && download_success=true
    fi
    
    if [[ "$download_success" == "false" ]]; then
        log_error "All download methods failed for $repo"
        return 1
    fi
    
    return 0
}

# Main download function
download_sensevoice_models() {
    log_info "🚀 Starting SenseVoice model download..."
    log_info "Model cache directory: $MODEL_CACHE_DIR"
    
    # Create cache directories
    mkdir -p "$MODEL_CACHE_DIR" "$HF_CACHE_DIR"
    
    # Download RKNN model (primary)
    local rknn_dir="$MODEL_CACHE_DIR/sensevoice-rknn"
    local rknn_path="$rknn_dir/$RKNN_MODEL"
    
    if check_model_integrity "$rknn_path" "$RKNN_SIZE_MB"; then
        log_info "✅ RKNN model already cached and valid"
    else
        log_info "📥 Downloading RKNN model..."
        if download_model "$RKNN_REPO" "$rknn_dir" "$RKNN_MODEL"; then
            if check_model_integrity "$rknn_path" "$RKNN_SIZE_MB"; then
                log_info "✅ RKNN model download and verification successful"
            else
                log_error "❌ RKNN model verification failed after download"
                return 1
            fi
        else
            log_error "❌ RKNN model download failed"
            return 1
        fi
    fi
    
    # Download ONNX model (optional backup)
    local onnx_dir="$MODEL_CACHE_DIR/sensevoice-onnx" 
    local onnx_path="$onnx_dir/$ONNX_MODEL"
    
    if check_model_integrity "$onnx_path" "$ONNX_SIZE_MB"; then
        log_info "✅ ONNX model already cached and valid"
    else
        log_info "📥 Downloading ONNX model (backup)..."
        if download_model "$ONNX_REPO" "$onnx_dir" "$ONNX_MODEL"; then
            if check_model_integrity "$onnx_path" "$ONNX_SIZE_MB"; then
                log_info "✅ ONNX model download and verification successful"
            else
                log_warn "⚠️ ONNX model verification failed (non-critical)"
            fi
        else
            log_warn "⚠️ ONNX model download failed (non-critical)"
        fi
    fi
    
    # Set permissions
    chmod -R 755 "$MODEL_CACHE_DIR"
    
    # Create model inventory
    cat > "$MODEL_CACHE_DIR/model_inventory.txt" << EOF
# SenseVoice Model Inventory
# Generated: $(date)

RKNN Model: $rknn_path
RKNN Size: $(stat -c%s "$rknn_path" 2>/dev/null || echo "0") bytes
RKNN Valid: $(check_model_integrity "$rknn_path" "$RKNN_SIZE_MB" && echo "YES" || echo "NO")

ONNX Model: $onnx_path  
ONNX Size: $(stat -c%s "$onnx_path" 2>/dev/null || echo "0") bytes
ONNX Valid: $(check_model_integrity "$onnx_path" "$ONNX_SIZE_MB" && echo "YES" || echo "NO")

Cache Directory: $MODEL_CACHE_DIR
HF Cache Directory: $HF_CACHE_DIR
EOF
    
    log_info "📋 Model inventory created: $MODEL_CACHE_DIR/model_inventory.txt"
    log_info "🎉 Model download process completed!"
    
    return 0
}

# Clean up corrupted models
cleanup_corrupted_models() {
    log_info "🧹 Cleaning up corrupted models..."
    
    local rknn_path="$MODEL_CACHE_DIR/sensevoice-rknn/$RKNN_MODEL"
    local onnx_path="$MODEL_CACHE_DIR/sensevoice-onnx/$ONNX_MODEL"
    
    # Check and remove corrupted RKNN model
    if [[ -f "$rknn_path" ]] && ! check_model_integrity "$rknn_path" "$RKNN_SIZE_MB"; then
        log_warn "Removing corrupted RKNN model: $rknn_path"
        rm -f "$rknn_path"
    fi
    
    # Check and remove corrupted ONNX model
    if [[ -f "$onnx_path" ]] && ! check_model_integrity "$onnx_path" "$ONNX_SIZE_MB"; then
        log_warn "Removing corrupted ONNX model: $onnx_path"
        rm -f "$onnx_path"
    fi
}

# Main execution
main() {
    case "${1:-download}" in
        "download")
            download_sensevoice_models
            ;;
        "cleanup")
            cleanup_corrupted_models
            ;;
        "check")
            log_info "Checking model integrity..."
            local rknn_path="$MODEL_CACHE_DIR/sensevoice-rknn/$RKNN_MODEL"
            if check_model_integrity "$rknn_path" "$RKNN_SIZE_MB"; then
                log_info "✅ Models are valid"
                exit 0
            else
                log_error "❌ Models are invalid or missing"
                exit 1
            fi
            ;;
        *)
            log_error "Usage: $0 [download|cleanup|check]"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"