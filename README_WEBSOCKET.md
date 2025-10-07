# 🎤 SenseVoice NPU Live Transcription with WebSocket Streaming

A complete real-time speech transcription system powered by Orange Pi 5 Max NPU with WebSocket streaming capabilities for live web dashboard viewing.

## 🌟 Features

- **🚀 NPU Acceleration**: Uses RK3588 NPU cores for fast SenseVoice inference (~330ms)
- **🎙️ Real-time Audio**: Live microphone input with automatic device selection
- **🌐 Web Dashboard**: Beautiful real-time web interface for transcription viewing
- **📡 WebSocket Streaming**: Real-time transcription broadcasting to connected clients
- **🔍 Confidence Filtering**: Shows only MEDIUM/HIGH confidence transcriptions
- **📊 Live Statistics**: Real-time metrics and performance tracking
- **🎯 Auto-configuration**: Automatic audio device detection and sample rate adjustment

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Microphone    │───▶│  NPU Processing │───▶│ WebSocket Server│
│   (48kHz)       │    │   (SenseVoice)  │    │   (Port 8765)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Web Dashboard  │◀───│   HTTP Server   │
                       │   (Live View)   │    │   (Port 8080)   │
                       └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Orange Pi 5 Max with RK3588 NPU
- RKNN drivers and runtime installed (`/usr/lib/librknnrt.so`)
- Docker and docker-compose
- USB microphone (AIRHUG recommended)

### Start Web Interface

```bash
# Clone/navigate to the project directory
cd sense_voice_full

# Start the complete web interface
./start_web.sh
```

### Access Dashboard

Once running, open your browser and navigate to:
- **Web Dashboard**: http://localhost:8080
- **WebSocket API**: ws://localhost:8765

## 📁 Project Structure

```
sense_voice_full/
├── src/
│   ├── live_transcription.py    # Main NPU transcription engine
│   ├── websocket_server.py      # WebSocket server for streaming
│   └── web_server.py           # HTTP server for web interface
├── web/
│   └── index.html              # Real-time dashboard frontend
├── scripts/
│   └── download_models.sh      # Model download automation
├── docker-compose.yml          # Docker orchestration
├── Dockerfile                  # Container definition
├── entrypoint.sh              # Container startup logic
└── start_web.sh               # Convenience startup script
```

## 🔧 Configuration

### Audio Device Selection

The system automatically detects and configures the AIRHUG USB microphone. To use a different device, modify the `AUDIO_DEVICE` environment variable in `docker-compose.yml`:

```yaml
environment:
  - AUDIO_DEVICE=YOUR_DEVICE_NAME
```

### Confidence Filtering

By default, only MEDIUM and HIGH confidence transcriptions are displayed. To show all transcriptions including LOW confidence, modify the confidence check in `live_transcription.py`.

### WebSocket Port

The WebSocket server runs on port 8765 by default. To change this, update both:
- `websocket_server.py` (server configuration)
- `web/index.html` (client connection URL)

## 🌐 Web Interface Features

### Real-time Dashboard
- **Live Transcriptions**: Streaming text updates as you speak
- **Confidence Badges**: Visual indicators for transcription quality
- **Auto-scroll**: Automatically follows latest transcriptions
- **Connection Status**: Real-time WebSocket connection monitoring

### Statistics Panel
- **Total Messages**: Count of all transcriptions received
- **High Confidence**: Count of high-quality transcriptions
- **Connection Time**: Duration of current WebSocket session

### Controls
- **Connect/Disconnect**: Manual WebSocket connection control
- **Clear**: Reset the transcription history
- **Auto-connect**: Automatically connects on page load

## 🔌 WebSocket API

The WebSocket server broadcasts transcription messages in JSON format:

```json
{
  "text": "The transcribed text",
  "confidence": "HIGH|MEDIUM|LOW",
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

### Client Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8765');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(`${data.confidence}: ${data.text}`);
};
```

## 🐳 Docker Commands

### Individual Services

```bash
# Live transcription only (no web interface)
docker-compose run --rm sensevoice-npu live-transcription

# Web interface with transcription
docker-compose run --rm --service-ports sensevoice-npu web-interface

# Model download only
docker-compose run --rm sensevoice-npu download-models

# Interactive shell for debugging
docker-compose run --rm sensevoice-npu bash
```

### Container Management

```bash
# Rebuild container after code changes
docker-compose build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Remove volumes (clears model cache)
docker-compose down -v
```

## 🛠️ Development

### Adding New Features

1. **Backend Changes**: Modify `live_transcription.py` for NPU processing
2. **WebSocket API**: Update `websocket_server.py` for new message types
3. **Frontend**: Enhance `web/index.html` for new UI features
4. **Container**: Update `Dockerfile` for new dependencies

### Testing WebSocket Connection

```bash
# Test WebSocket server directly
python3 -c "
import asyncio
import websockets

async def test_client():
    uri = 'ws://localhost:8765'
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            print(f'Received: {message}')

asyncio.run(test_client())
"
```

## 📊 Performance Metrics

- **NPU Inference**: ~330ms average processing time
- **WebSocket Latency**: <10ms for local connections
- **Memory Usage**: ~2GB during active transcription
- **CPU Usage**: ~15% (most processing on NPU)

## 🔍 Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check if port 8765 is available
   - Verify container is running with host networking
   - Check firewall settings

2. **No Audio Input Detected**
   - Verify microphone is connected and recognized
   - Check Docker audio device mounting
   - Test with `arecord -l` inside container

3. **NPU Inference Errors**
   - Verify NPU device access (`/dev/dri/renderD129`)
   - Check RKNN runtime library (`/usr/lib/librknnrt.so`)
   - Review container privileges and device mounting

4. **Web Dashboard Not Loading**
   - Check if port 8080 is available
   - Verify HTTP server is running
   - Check browser console for errors

### Debug Mode

```bash
# Start with debug logging
LOG_LEVEL=DEBUG ./start_web.sh

# View detailed container logs
docker-compose logs -f
```

## 📝 License

This project is part of the NPU smoke test suite for Orange Pi 5 Max development.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your enhancements
4. Test with the provided smoke tests
5. Submit a pull request

---

**Happy Transcribing! 🎤✨**