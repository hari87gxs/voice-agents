# Vernac - GXS Bank Voice-to-Voice Debt Collection Agent

A state-of-the-art voice AI platform for debt collection using Azure OpenAI GPT-4o Realtime API with ultra-low latency and natural conversational capabilities.

## 🎯 Overview

Vernac is a professional voice agent that conducts real-time, interruptible conversations for debt collection on behalf of GXS Bank. The system features:

- **Real-time Voice Communication**: WebSocket-based low-latency audio streaming
- **Natural Interruptions**: True barge-in capability using Azure's Server VAD
- **Singlish-Enhanced Persona**: Professional yet locally adapted conversational style
- **High-Fidelity Audio**: PCM16 24kHz pipeline with proper DSP resampling
- **Compliance-First Design**: Built-in legal disclaimers and structured negotiation flow

## 🏗️ Architecture

```
Browser (48kHz) → AudioWorklet (Linear Interpolation) → 24kHz PCM16
                                    ↓
                            WebSocket Client
                                    ↓
                         FastAPI Relay Server
                                    ↓
                         Azure OpenAI Realtime API
                                    ↓
                         FastAPI Relay Server
                                    ↓
                            WebSocket Client
                                    ↓
              Audio Playback (with Interruption Support)
```

## 📋 Prerequisites

- Python 3.9+
- Modern browser with WebSocket and AudioWorklet support (Chrome 66+, Edge 79+, Safari 14.1+)
- Azure OpenAI account with GPT-4o Realtime API access

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone or navigate to the project
cd Vernac

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Azure OpenAI

Edit `.env` with your Azure OpenAI credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-realtime-preview
```

### 3. Run the Server

```bash
python server.py
```

The server will start on `http://localhost:8000`

### 4. Open the Client

Navigate to `http://localhost:8000` in your browser and click "Start Call" to begin a conversation.

## 🎛️ Technical Specifications

### Audio Pipeline
- **Input Format**: Browser native (typically 48kHz Float32 Stereo)
- **Processing**: Linear interpolation downsampling to 24kHz Mono PCM16
- **Output Format**: 24kHz Mono PCM16 Little Endian
- **Latency Target**: < 500ms end-to-end

### Key Features

#### 1. **Linear Interpolation Resampling**
The AudioWorklet processor (`audio-processor.js`) implements proper DSP techniques:
- Avoids simple decimation (sample dropping)
- Uses linear interpolation: `val = s[idx] + (s[idx+1] - s[idx]) * (pos - idx)`
- Prevents audio artifacts and aliasing

#### 2. **Interruption Handling (Barge-In)**
- Server forwards `input_audio_buffer.speech_started` events immediately
- Client flushes audio playback queue on interruption detection
- Enables natural conversation flow without talking over the user

#### 3. **Server VAD Configuration**
```json
{
  "type": "server_vad",
  "threshold": 0.6,
  "prefix_padding_ms": 300,
  "silence_duration_ms": 600,
  "create_response": true
}
```

## 💬 Conversation Flow

The GXS Collector follows a structured waterfall negotiation:

1. **Compliance Opening**: Legal disclaimer and account notification
2. **Initial Request**: 3-day payment timeline
3. **First Fallback**: 7-day payment option
4. **Final Warning**: Credit rating impact notice
5. **Edge Case Handling**: Financial difficulty referrals, partial payment guidance

## 📁 Project Structure

```
Vernac/
├── server.py              # FastAPI WebSocket relay server
├── index.html             # Main web interface
├── client.js              # Frontend WebSocket and audio handling
├── audio-processor.js     # AudioWorklet for DSP resampling
├── requirements.txt       # Python dependencies
├── package.json           # Project metadata
├── .env.example           # Environment template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── ARCHITECTURE.md       # System architecture documentation
├── CODE_EXPLANATION.md   # Detailed code walkthrough
└── test_e2e.py          # End-to-end test suite
```

## 🧪 Testing

Run the end-to-end test suite:

```bash
python test_e2e.py
```

This validates:
- WebSocket connectivity
- Audio format compliance (PCM16 24kHz)
- Session configuration
- Interruption event handling
- Latency measurements

## 🔒 Security & Compliance

- All conversations include mandatory legal disclaimers
- API keys stored in environment variables (never committed)
- CORS protection enabled
- Structured escalation paths for vulnerable customers

## 🛠️ Troubleshooting

### Microphone Not Working
- Ensure HTTPS or localhost (required for getUserMedia)
- Check browser permissions for microphone access

### High Latency
- Verify network connection to Azure
- Check browser console for WebSocket errors
- Monitor server logs for relay delays

### Audio Quality Issues
- Confirm browser is using 48kHz sample rate
- Check AudioWorklet is properly loaded
- Verify PCM16 format in Azure configuration

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System design and data flow
- **[CODE_EXPLANATION.md](CODE_EXPLANATION.md)**: Detailed code walkthrough

## 🔧 Development

### Key Components

1. **server.py**: Stateless WebSocket relay with Azure OpenAI integration
2. **audio-processor.js**: DSP processing with linear interpolation
3. **client.js**: Audio capture, playback queue, and interruption handling
4. **index.html**: Modern UI with transcript display and download

### Adding Features

- Modify system instructions in `server.py` (line ~50-80)
- Adjust VAD sensitivity in session configuration
- Customize UI in `index.html`

## 📄 License

Proprietary - GXS Bank

## 🤝 Support

For issues or questions:
- Email: help@gxs.com.sg
- Internal: Contact GXS AI Team

---

**Built with ❤️ by the GXS AI Team**
