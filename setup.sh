#!/bin/bash
#
# 🚀 SenseVoice Full Setup Script
# ===============================
# Complete setup and deployment script for NPU-accelerated live transcription
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="sensevoice-npu"
CACHE_BASE_DIR="$SCRIPT_DIR/model_cache"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $*"
}

# Prerequisites check
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check if we can write to current directory
    if [[ ! -w "$SCRIPT_DIR" ]]; then
        log_error "Cannot write to current directory: $SCRIPT_DIR"
        return 1
    fi
    
    # Check Docker
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    # Check Docker Compose (supports both v1 and v2)
    if command -v docker-compose >/dev/null 2>&1; then
        log_info "Found Docker Compose v1 (docker-compose)"
    elif docker compose version >/dev/null 2>&1; then
        log_info "Found Docker Compose v2 (docker compose)"
    else
        log_error "Docker Compose is not installed or not in PATH"
        log_error "Please install Docker Compose: https://docs.docker.com/compose/install/"
        return 1
    fi
    
    # Check NPU device
    if [[ ! -c /dev/rknpu ]]; then
        log_error "NPU device /dev/rknpu not found"
        log_error "Make sure you're running on Orange Pi 5 Max with NPU drivers installed"
        return 1
    fi
    
    # Check RKNN library
    if [[ ! -f /usr/lib/librknnrt.so ]]; then
        log_error "RKNN runtime library not found: /usr/lib/librknnrt.so"
        log_error "Please install NPU runtime libraries"
        return 1
    fi
    
    log_info "✅ Prerequisites check passed"
    return 0
}

# Setup system directories
setup_directories() {
    log_step "Setting up cache directories..."
    
    # Create cache directories
    mkdir -p "$CACHE_BASE_DIR"/{models,cache,logs}
    
    # Set proper permissions
    chmod -R 755 "$CACHE_BASE_DIR"
    
    log_info "✅ Cache directories created:"
    log_info "   Models: $CACHE_BASE_DIR/models"
    log_info "   Cache:  $CACHE_BASE_DIR/cache"
    log_info "   Logs:   $CACHE_BASE_DIR/logs"
}

# Build Docker image
build_image() {
    log_step "Building SenseVoice Docker image..."
    
    cd "$SCRIPT_DIR"
    
    # Build with cache and progress
    docker build \
        --tag "$PROJECT_NAME:latest" \
        --progress=plain \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        .
    
    log_info "✅ Docker image built successfully"
}

# Test NPU access  
test_npu_access() {
    log_step "Testing NPU device access..."
    
    # Run basic NPU device test (without requiring models)
    if docker run --rm --privileged \
        -v /usr/lib/librknnrt.so:/usr/lib/librknnrt.so:ro \
        -v /dev/rknpu:/dev/rknpu \
        "$PROJECT_NAME:latest" \
        health device; then
        log_info "✅ NPU device access test passed"
    else
        log_error "❌ NPU device access test failed"
        return 1
    fi
}

# Download models
download_models() {
    log_step "Downloading SenseVoice models..."
    
    # Download models using container
    docker run --rm \
        -v "$CACHE_BASE_DIR/models:/app/models" \
        -v "$CACHE_BASE_DIR/cache:/app/cache" \
        "$PROJECT_NAME:latest" \
        download-models
    
    log_info "✅ Models downloaded and cached"
}

# Run health check
run_health_check() {
    log_step "Running comprehensive health check..."
    
    # Full health check
    if docker run --rm --privileged \
        -v /usr/lib/librknnrt.so:/usr/lib/librknnrt.so:ro \
        -v /dev/rknpu:/dev/rknpu \
        -v "$CACHE_BASE_DIR/models:/app/models" \
        -v "$CACHE_BASE_DIR/cache:/app/cache" \
        "$PROJECT_NAME:latest" \
        health full; then
        log_info "✅ Health check passed"
    else
        log_error "❌ Health check failed"
        return 1
    fi
}

# Start services with Docker Compose (with web interface)
start_services() {
    log_step "Starting SenseVoice web interface..."
    
    cd "$SCRIPT_DIR"
    
    # Update docker-compose.yml with correct paths
    export SENSEVOICE_MODELS_PATH="$CACHE_BASE_DIR/models"
    export SENSEVOICE_CACHE_PATH="$CACHE_BASE_DIR/cache"
    export SENSEVOICE_LOGS_PATH="$CACHE_BASE_DIR/logs"
    
    # Detect Docker Compose command (v1 or v2)
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Docker Compose is not installed"
        return 1
    fi
    
    log_info "Using Docker Compose command: $DOCKER_COMPOSE"
    
    # Stop any existing container
    $DOCKER_COMPOSE down 2>/dev/null || true
    
    # Start with web interface command
    log_info "Starting services in background..."
    $DOCKER_COMPOSE up -d
    
    # Wait for services to be ready
    sleep 3
    
    log_info "✅ Services started successfully"
    echo ""
    log_info "🌐 Web interface is running!"
    echo ""
    echo "Access URLs:"
    echo "  📊 Web Dashboard: http://localhost:8080"
    echo "  🔌 WebSocket API: ws://localhost:8765"
    echo ""
    echo "Features:"
    echo "  • Real-time NPU transcription display"
    echo "  • Live WebSocket streaming"
    echo "  • Confidence level filtering"
    echo "  • Interactive dashboard"
    echo ""
    log_info "� View logs with: $0 logs"
    log_info "🛑 Stop with: $0 stop"
}

# Show usage information
show_usage() {
    cat << EOF
🚀 SenseVoice NPU Live Transcription Setup

Usage: $0 [COMMAND]

Commands:
  setup     - Complete setup (default)
  build     - Build Docker image only
  test      - Test NPU access
  download  - Download models only
  health    - Run health check
  start     - Start web interface with transcription (default mode)
  web       - Alias for 'start' - starts web interface
  stop      - Stop services
  restart   - Restart services
  logs      - Show live logs
  clean     - Clean up containers and images

Examples:
  $0 setup      # Complete setup and start
  $0 start      # Start web interface with dashboard
  $0 logs       # View live transcription output
  $0 restart    # Restart the service
EOF
}

# Stop services
stop_services() {
    log_step "Stopping SenseVoice services..."
    
    cd "$SCRIPT_DIR"
    
    # Detect Docker Compose command
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Docker Compose is not installed"
        return 1
    fi
    
    $DOCKER_COMPOSE down
    
    log_info "✅ Services stopped"
}

# Restart services
restart_services() {
    log_step "Restarting services with rebuild..."
    stop_services
    build_image
    start_services
}

# Show logs
show_logs() {
    log_info "📊 Showing live transcription logs..."
    log_info "Press Ctrl+C to exit log view"
    docker logs -f sensevoice-live
}

# Start web interface
start_web_interface() {
    # Web interface is now the default, so just call start_services
    start_services
}

# Clean up
cleanup() {
    log_step "Cleaning up containers and images..."
    
    # Stop services
    stop_services 2>/dev/null || true
    
    # Remove containers
    docker rm -f sensevoice-live 2>/dev/null || true
    
    # Remove images
    docker rmi "$PROJECT_NAME:latest" 2>/dev/null || true
    
    log_info "✅ Cleanup completed"
}

# Complete setup
complete_setup() {
    log_info "🚀 Starting complete SenseVoice setup..."
    log_info "This will:"
    log_info "  1. Check prerequisites"
    log_info "  2. Create cache directories"
    log_info "  3. Build Docker image"
    log_info "  4. Download models"
    log_info "  5. Test NPU device access"
    log_info "  6. Run comprehensive health check"
    log_info "  7. Start live transcription"
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled"
        exit 0
    fi
    
    check_prerequisites
    setup_directories
    build_image
    download_models
    test_npu_access
    run_health_check
    start_services
    
    log_info "🎉 Setup completed successfully!"
    log_info ""
    log_info "📋 Next steps:"
    log_info "  • View transcription: $0 logs"
    log_info "  • Stop service: $0 stop"
    log_info "  • Restart service: $0 restart"
    log_info ""
    log_info "🎙️ The system is now listening for audio and will output transcriptions to the logs."
}

# Main command dispatcher
main() {
    case "${1:-setup}" in
        "setup")
            complete_setup
            ;;
        "build")
            check_prerequisites
            build_image
            ;;
        "test")
            test_npu_access
            ;;
        "download")
            setup_directories
            download_models
            ;;
        "health")
            run_health_check
            ;;
        "start")
            start_services
            ;;
        "web")
            start_web_interface
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        "logs")
            show_logs
            ;;
        "clean")
            cleanup
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"