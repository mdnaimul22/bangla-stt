# Whisper STT Service

Standalone, high-performance Speech-to-Text API service built with FastAPI, PyTorch, Whisper, Hugging Face Transformers, and Spectral Noise Reduction.

---

## Features

- **OpenAI-Compatible Endpoint**: `POST /v1/audio/transcriptions` supporting standard `multipart/form-data` audio file uploads (`file`, `model`, `language`, `noise_reduction`).
- **Base64 JSON Endpoint**: `POST /v1/audio/transcriptions/json` for microservices sending base64-encoded audio.
- **Native Bengali Model**: Preloaded with `shhossain/whisper-base-bn` for high-accuracy Bengali speech recognition.
- **Spectral Noise Reduction**: Integrated `noisereduce` spectral gating toggle (`prop_decrease=0.75`) to suppress background noise.
- **Multi-Format Audio**: Decodes WebM (Opus), WAV, MP3, M4A, OGG, FLAC via high-speed ffmpeg pipeline.
- **Bearer Token Security**: Constant-time `hmac.compare_digest` authentication header validation.
- **Tailscale Funnel Ready**: Automatically accessible publicly over your Tailscale node URL or intranet IP.

---

## Project Structure

```
whisper-service/
├── .env                     # Runtime environment driver (API_KEY, HOST, PORT, DEFAULT_MODEL)
├── .env.example             # Configuration blueprint template
├── main.py                  # FastAPI server entry point with lifespan and port guard
├── src/
│   ├── config/              # Single source of truth (Settings, sandboxed files, logger)
│   ├── schema/              # Pydantic data contracts (TranscriptionResponse, HealthResponse)
│   ├── helpers/             # Stateless audio decoding, spectral noise reduction, and auth
│   ├── services/            # TranscriberService model cache and multi-backend inference
│   └── routers/             # HTTP endpoints (/v1/audio/transcriptions, /v1/audio/transcriptions/json, /health)
└── tests/                   # Pytest automated test suite
```

---

## Configuration (`.env`)

```ini
APP_ENV=development
LOG_DIR=logs
DATA_DIR=data

API_HOST=0.0.0.0
API_PORT=8020

API_KEY=sk-whisper-bn-secret

DEFAULT_MODEL=shhossain/whisper-base-bn
DEFAULT_LANGUAGE=bn
NOISE_REDUCTION_DEFAULT=true
```

---

## Quickstart

### 1. Start the Server
```bash
cd /home/naimul/whisper-service
./.venv/bin/python main.py
```

### 2. Verify Health
```bash
curl -s http://127.0.0.1:8020/health | jq
```

---

## API Usage Examples

### 1. Standard Multipart Upload (OpenAI Compatible)
```bash
curl -X POST http://127.0.0.1:8020/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-whisper-bn-secret" \
  -F "file=@audio.webm" \
  -F "model=shhossain/whisper-base-bn" \
  -F "language=bn" \
  -F "noise_reduction=true"
```

**Response (`200 OK`):**
```json
{
  "text": "আপনার বাংলা কথার ট্রান্সক্রিপশন",
  "language": "bn",
  "model": "shhossain/whisper-base-bn",
  "noise_reduction": true,
  "duration_seconds": 1.25
}
```

### 2. Base64 JSON Payload
```bash
curl -X POST http://127.0.0.1:8020/v1/audio/transcriptions/json \
  -H "Authorization: Bearer sk-whisper-bn-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "GkXfo59ChoEBQveBAULygQ8...",
    "model": "shhossain/whisper-base-bn",
    "language": "bn",
    "noise_reduction": true
  }'
```

---

## Running Automated Tests

```bash
cd /home/naimul/whisper-service
./.venv/bin/python -m pytest tests/test_transcription.py -v
```
