#!/bin/bash
#
# 🌐 Start SenseVoice Web Interface
# ==================================
# Convenience script to start the complete web-enabled transcription system
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Configuration
CONTAINER_NAME="sensevoice-live"
WEB_PORT="8080"
WS_PORT="8765"

print_banner() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "🎤 SenseVoice NPU Live Transcription Web Interface"
    echo "=================================================="
    echo -e "${NC}"
    echo "Features:"
    echo "  🚀 NPU-accelerated inference (Orange Pi 5 Max)"
    echo "  🎙️ Real-time audio transcription"
    echo "  🌐 Web dashboard for live results"
    echo "  📊 Confidence filtering & statistics"
    echo ""
}

check_requirements() {
    log_info "Checking system requirements..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if docker-compose is available (supports both v1 and v2)
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "docker-compose is not installed or not in PATH"
        log_error "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    log_info "Using Docker Compose command: $DOCKER_COMPOSE"
    
    # Check NPU device access
    if [[ ! -e /dev/dri/renderD129 ]] && [[ ! -e /dev/rknpu ]]; then
        log_error "NPU device not found (/dev/dri/renderD129 or /dev/rknpu)"
        log_error "Make sure you're running on Orange Pi 5 Max with NPU drivers installed"
        exit 1
    fi
    
    # Check RKNN runtime library
    if [[ ! -f /usr/lib/librknnrt.so ]]; then
        log_error "RKNN runtime library not found: /usr/lib/librknnrt.so"
        log_error "Please install RKNN drivers and runtime"
        exit 1
    fi
    
    log_success "All requirements satisfied"
}

build_container() {
    log_info "Building container image..."
    
    if $DOCKER_COMPOSE build; then
        log_success "Container built successfully"
    else
        log_error "Container build failed"
        exit 1
    fi
}

start_services() {
    log_info "Starting SenseVoice web interface..."
    
    # Stop any existing container
    $DOCKER_COMPOSE down 2>/dev/null || true
    
    # Start with web interface command
    if $DOCKER_COMPOSE run --rm --service-ports "$CONTAINER_NAME" web-interface; then
        log_success "Services started successfully"
    else
        log_error "Failed to start services"
        exit 1
    fi
}

show_access_info() {
    echo ""
    log_success "🌐 SenseVoice Web Interface is running!"
    echo ""
    echo "Access URLs:"
    echo "  📊 Web Dashboard: http://localhost:$WEB_PORT"
    echo "  🔌 WebSocket API: ws://localhost:$WS_PORT"
    echo ""
    echo "Features:"
    echo "  • Real-time NPU transcription display"
    echo "  • Confidence level filtering"
    echo "  • Live statistics and metrics"
    echo "  • Auto-connecting WebSocket client"
    echo ""
    echo "Audio Setup:"
    echo "  🎤 Configured for AIRHUG USB microphone"
    echo "  📡 Automatic sample rate detection (48kHz)"
    echo "  🔇 Voice Activity Detection enabled"
    echo ""
    echo "Press Ctrl+C to stop the service"
    echo ""
}

# Main execution
main() {
    print_banner
    check_requirements
    build_container
    
    # Show access information before starting
    show_access_info
    
    # Start services (this will block)
    start_services
}

# Handle script interruption
trap 'log_info "Shutting down..."; $DOCKER_COMPOSE down; exit 0' INT TERM

# Execute main function
main "$@"