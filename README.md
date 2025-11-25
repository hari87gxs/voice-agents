# Voice Agents Platform

Multi-persona voice AI platform using Azure OpenAI GPT-4o Realtime API. Production-ready conversational AI with real-time, interruptible voice interactions.

## 🚀 Deployed Applications

All applications are live on Google Cloud Run:

1. **Vernac (ABC Bank Debt Collector)**
   - URL: https://vernac-voice-agent-708533464468.us-central1.run.app
   - Persona: Debt collection with waterfall negotiation, Singlish tone, compliance rules
   - Voice: Cedar

2. **Newton (Science Teacher)**
   - URL: https://newton-science-teacher-708533464468.us-central1.run.app
   - Persona: Kid-friendly science teacher for 7-year-olds with enthusiasm and analogies
   - Voice: Shimmer

3. **Bheema (Metabolic Health Coach)**
   - URL: https://bheema-health-coach-708533464468.us-central1.run.app
   - Persona: Metabolic health and performance coach with endocrinology expertise
   - Voice: Cedar

## 📋 Features

- **Real-time Voice Conversations**: Low-latency, interruptible voice interactions
- **Azure OpenAI Integration**: GPT-4o Realtime API with advanced voice capabilities
- **Multi-Persona Architecture**: Config-driven persona system for easy customization
- **Production Deployment**: Containerized apps on Google Cloud Run
- **High-Quality Audio**: PCM16 24kHz mono with custom DSP processing
- **Long Session Support**: 1-hour timeout, no CPU throttling
- **WebSocket Communication**: Stable, stateless relay architecture

## 🏗️ Architecture

### Technology Stack
- **Backend**: Python 3.11, FastAPI 0.104.1, WebSockets 12.0
- **Frontend**: Vanilla JavaScript with AudioWorklet API
- **AI**: Azure OpenAI GPT-4o Realtime API
- **Audio**: PCM16 24kHz mono, linear interpolation DSP (48kHz→24kHz)
- **Deployment**: Docker, Google Cloud Run
- **Infrastructure**: GCP Project vernac-479217

### Components

```
┌─────────────────┐     WebSocket      ┌──────────────┐     WebSocket     ┌─────────────────┐
│   Browser UI    │ ←─────────────────→ │ FastAPI      │ ←────────────────→ │  Azure OpenAI   │
│                 │                     │ Server       │                    │  Realtime API   │
│ - Audio Capture │   Base64 PCM16     │              │   Base64 PCM16    │                 │
│ - AudioWorklet  │                     │ - Config     │                    │ - GPT-4o        │
│ - Playback      │                     │ - Relay      │                    │ - TTS/STT       │
└─────────────────┘                     └──────────────┘                    └─────────────────┘
```

### Audio Pipeline

1. **Input**: Browser mic → MediaRecorder → PCM16 48kHz
2. **DSP**: AudioWorklet linear interpolation → 24kHz
3. **Transport**: WebSocket base64 encoding
4. **Processing**: Azure OpenAI Realtime API
5. **Output**: Base64 PCM16 24kHz → Float32 → AudioBuffer → Playback

## 📁 Repository Structure

```
├── Vernac/              # ABC Bank debt collector
│   ├── server.py        # FastAPI WebSocket relay
│   ├── config.json      # Persona configuration
│   ├── index.html       # Frontend UI
│   ├── client.js        # WebSocket client + audio
│   ├── audio-processor.js  # AudioWorklet DSP
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── DEPLOYMENT.md
│   ├── ARCHITECTURE.md
│   ├── CONFIG_GUIDE.md
│   └── CODE_EXPLANATION.md
│
├── Newton/              # Science teacher for kids
│   ├── server.py
│   ├── config.json
│   ├── index.html
│   ├── client.js
│   ├── audio-processor.js
│   ├── requirements.txt
│   ├── Dockerfile
│   └── DEPLOYMENT_GUIDE.md
│
├── Bheema/              # Metabolic health coach
│   ├── server.py
│   ├── config.json
│   ├── index.html
│   ├── client.js
│   ├── audio-processor.js
│   ├── requirements.txt
│   ├── Dockerfile
│   └── DEPLOYMENT_GUIDE.md
│
└── README.md            # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Azure OpenAI account with GPT-4o Realtime API access
- Google Cloud SDK (for deployment)
- Docker (for containerization)

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/hari87gxs/voice-agents.git
cd voice-agents
```

2. **Choose an app and navigate to its directory**
```bash
cd Vernac  # or Newton, or Bheema
```

3. **Create `.env` file**
```bash
cat > .env << EOF
AZURE_OPENAI_ENDPOINT=your-endpoint-here
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-realtime
PORT=8000
EOF
```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Run the server**
```bash
python3 server.py
```

6. **Open browser**
```
http://localhost:8000
```

## 🎨 Creating New Personas

See `DEPLOYMENT_GUIDE.md` in any app directory for comprehensive instructions. Quick overview:

1. **Copy an existing app directory**
```bash
cp -r Vernac MyNewPersona
cd MyNewPersona
```

2. **Edit `config.json`**
   - Change `role`, `goal`, `voice`
   - Customize conversation phases
   - Add domain-specific rules

3. **Update `index.html`**
   - Modify branding, colors, emojis
   - Update title and header text

4. **Test locally**
```bash
python3 server.py
```

5. **Deploy to Cloud Run**
```bash
docker build --platform=linux/amd64 -t gcr.io/vernac-479217/my-persona .
docker push gcr.io/vernac-479217/my-persona
gcloud run deploy my-persona --image gcr.io/vernac-479217/my-persona ...
```

## 🔧 Configuration

### Server Settings (`config.json`)

```json
{
  "system_prompt": {
    "role": "Your Persona Name",
    "goal": "Primary objective",
    "voice": "shimmer|cedar|alloy|echo",
    "intro_message": "Opening greeting",
    "tone": "Communication style",
    "core_rules": ["Rule 1", "Rule 2"]
  },
  "conversation_script": {
    "phase_1_greeting": {
      "title": "Phase Title",
      "objective": "What to achieve"
    }
  }
}
```

### Cloud Run Settings

- **Timeout**: 3600s (1 hour)
- **Memory**: 512Mi
- **CPU**: 1
- **CPU Throttling**: Disabled
- **Port**: 8000
- **Region**: us-central1

## 📚 Documentation

Each app includes comprehensive documentation:

- **ARCHITECTURE.md**: Technical architecture details
- **DEPLOYMENT.md**: Deployment guide and troubleshooting
- **CONFIG_GUIDE.md**: Configuration reference
- **CODE_EXPLANATION.md**: Code walkthrough
- **DEPLOYMENT_GUIDE.md**: Step-by-step persona creation

## 🛠️ Technical Details

### Server (server.py)
- **Framework**: FastAPI with WebSocket support
- **Pattern**: Stateless relay (no session storage)
- **Config Parsing**: Dynamic loop supports any phase structure
- **Error Handling**: Comprehensive try-catch with logging

### Client (client.js)
- **Audio Capture**: MediaRecorder API
- **Processing**: AudioWorklet for DSP
- **Playback**: Web Audio API with crossfading
- **Protocol**: Auto-detection (ws:// or wss://)

### Audio Processor (audio-processor.js)
- **Algorithm**: Linear interpolation resampling
- **Input**: 48kHz Float32
- **Output**: 24kHz PCM16
- **Performance**: Runs on separate thread

## 🔐 Environment Variables

Required for all deployments:

```bash
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-realtime
PORT=8000  # Local only, Cloud Run uses 8000
```

## 🐛 Troubleshooting

### Session Disconnects
- Timeout set to 3600s (1 hour max)
- Check Cloud Run logs: `gcloud run services logs read <service-name>`

### Audio Quality Issues
- Ensure 24kHz PCM16 format
- Check network latency
- Verify Azure OpenAI region proximity

### Voice Not Working
- Supported voices: shimmer, cedar, alloy, echo
- NOT supported: nova, onyx
- Check voice setting in `config.json`

### Config Parsing Errors
- Validate JSON syntax
- Ensure all phases have `title` field
- Check for missing quotes/commas

## 📊 Performance

- **Latency**: ~200-500ms round-trip
- **Audio Quality**: 24kHz mono PCM16
- **Session Duration**: Up to 1 hour
- **Concurrent Users**: Scales with Cloud Run instances

## 🚢 Deployment Commands

```bash
# Build Docker image
docker build --platform=linux/amd64 -t gcr.io/vernac-479217/app-name .

# Push to Google Container Registry
docker push gcr.io/vernac-479217/app-name

# Deploy to Cloud Run
source .env && gcloud run deploy app-name \
  --image gcr.io/vernac-479217/app-name \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT \
  --port 8000 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 3600 \
  --no-cpu-throttling \
  --quiet
```

## 📝 License

MIT License - See individual app directories for details.

## 🤝 Contributing

This is a production platform. For changes:
1. Test locally first
2. Update relevant documentation
3. Deploy to staging (if available)
4. Monitor Cloud Run logs

## 📧 Contact

For issues or questions, please use GitHub Issues.

---

**Platform Status**: Production ✅  
**Last Updated**: November 25, 2025  
**Version**: 1.0.0
