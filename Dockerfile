FROM ubuntu:22.04

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# Create application directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    portaudio19-dev \
    alsa-utils \
    pulseaudio-utils \
    git \
    wget \
    curl \
    unzip \
    build-essential \
    cmake \
    pkg-config \
    libasound2-dev \
    libportaudio2 \
    libsndfile1 \
    ffmpeg \
    git-lfs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Install core packages
RUN pip3 install --no-cache-dir \
    numpy>=1.22.3 \
    scipy>=1.6.0 \
    opencv-python \
    pillow \
    pyaudio \
    librosa>=0.10.0 \
    soundfile \
    torch \
    transformers \
    huggingface-hub \
    tqdm \
    requests \
    sentencepiece \
    kaldi-native-fbank \
    websockets \
    asyncio

# Install RKNN toolkit
RUN pip3 install --no-cache-dir \
    rknn-toolkit-lite2==2.3.2

# Create model cache directory
RUN mkdir -p /app/models /app/cache /app/logs

# Copy application files
COPY scripts/ /app/scripts/
COPY src/ /app/src/
COPY web/ /app/web/
COPY entrypoint.sh /app/
COPY healthcheck.sh /app/

# Make scripts executable
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh /app/scripts/*.sh

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash sensevoice && \
    chown -R sensevoice:sensevoice /app && \
    usermod -a -G audio,video sensevoice

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/healthcheck.sh

# Switch to non-root user
USER sensevoice

# Expose any ports if needed (for WebSocket and web interface)
EXPOSE 8080 8765

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["live-transcription"]