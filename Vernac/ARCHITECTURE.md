# Vernac Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Technical Decisions](#technical-decisions)
6. [Performance Optimization](#performance-optimization)
7. [Security Considerations](#security-considerations)

---

## System Overview

Vernac is a real-time voice-to-voice conversational AI platform designed for debt collection at GXS Bank. The system enables natural, interruptible conversations with ultra-low latency using Azure OpenAI's GPT-4o Realtime API.

### Key Characteristics
- **Architecture Pattern**: WebSocket Relay (Pass-through)
- **Latency Target**: < 500ms end-to-end
- **Audio Format**: PCM16, 24kHz, Mono, Little Endian
- **Conversation Style**: Professional with Singlish-enhanced persona
- **Interruption Model**: Server VAD with client-side audio queue flushing

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (Client)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌─────────────────┐                     │
│  │  Microphone  │ ───> │ AudioWorklet    │                     │
│  │  (48kHz)     │      │ - Downsample    │                     │
│  └──────────────┘      │ - Float32→PCM16 │                     │
│                        │ - Linear Interp │                     │
│                        └────────┬────────┘                     │
│                                 │ PCM16 24kHz                   │
│                                 ▼                               │
│                        ┌─────────────────┐                     │
│                        │  WebSocket      │                     │
│                        │  Client         │                     │
│                        └────────┬────────┘                     │
│                                 │                               │
└─────────────────────────────────┼───────────────────────────────┘
                                  │
                                  │ WSS Connection
                                  │
┌─────────────────────────────────┼───────────────────────────────┐
│                        FastAPI Server (Relay)                    │
├─────────────────────────────────┼───────────────────────────────┤
│                                 │                               │
│                        ┌────────▼────────┐                     │
│                        │  WebSocket      │                     │
│                        │  Endpoint       │                     │
│                        │  /ws/chat       │                     │
│                        └────────┬────────┘                     │
│                                 │                               │
│                    ┌────────────┴────────────┐                 │
│                    │                         │                 │
│           ┌────────▼────────┐       ┌───────▼────────┐        │
│           │ Browser→Azure   │       │ Azure→Browser  │        │
│           │ Relay Task      │       │ Relay Task     │        │
│           │ (Bidirectional) │       │ (Interruption  │        │
│           │                 │       │  Detection)    │        │
│           └────────┬────────┘       └───────┬────────┘        │
│                    │                         │                 │
└────────────────────┼─────────────────────────┼─────────────────┘
                     │                         │
                     │    WSS Connection       │
                     │                         │
┌────────────────────┼─────────────────────────┼─────────────────┐
│              Azure OpenAI Realtime API                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  GPT-4o Realtime Model                                   │  │
│  │  - Audio Input (PCM16 24kHz)                            │  │
│  │  - Audio Output (PCM16 24kHz)                           │  │
│  │  - Server VAD (Voice Activity Detection)                │  │
│  │  - Transcription (Whisper)                              │  │
│  │  - System Instructions (GXS Collector Persona)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘


                      ┌──────────────────────┐
                      │   Data Flow Legend   │
                      ├──────────────────────┤
                      │  ───>  Audio         │
                      │  ━━━>  Events/JSON   │
                      │  ═══>  Both          │
                      └──────────────────────┘
```

---

## Component Design

### 1. Browser Client (`client.js`)

**Responsibilities:**
- Capture microphone audio
- Manage WebSocket connection
- Queue and play audio responses
- Handle interruptions (barge-in)
- Display transcripts and UI updates

**Key Classes:**
```javascript
class VernacVoiceClient {
    - ws: WebSocket
    - audioContext: AudioContext
    - audioQueue: Array<ArrayBuffer>
    - transcript: Array<Object>
    
    Methods:
    - startCall(): Initialize microphone and WebSocket
    - handleBargeIn(): Flush audio queue on interruption
    - playNextAudioChunk(): Manage audio playback queue
    - addToTranscript(): Update conversation history
}
```

**State Management:**
- `isConnected`: WebSocket connection state
- `isRecording`: Microphone capture state
- `isPlaying`: Audio playback state
- `audioQueue`: Pending audio chunks to play

### 2. AudioWorklet Processor (`audio-processor.js`)

**Responsibilities:**
- Resample from browser native rate (48kHz) to 24kHz
- Convert Float32 to PCM16
- Stereo to Mono conversion
- Buffer management and chunking

**Key Algorithm: Linear Interpolation**
```
For each output sample at position i:
  1. Calculate source position: pos = i * (sourceRate / targetRate)
  2. Get integer index: idx = floor(pos)
  3. Get fractional part: frac = pos - idx
  4. Interpolate: output[i] = input[idx] + (input[idx+1] - input[idx]) * frac
```

**Processing Pipeline:**
```
Input (48kHz Float32 Stereo)
    │
    ├─> Stereo to Mono (average channels)
    │
    ├─> Linear Interpolation Resampling
    │   (48kHz → 24kHz)
    │
    ├─> Float32 to PCM16 Conversion
    │   (-1.0 to 1.0 → -32768 to 32767)
    │
    └─> Output (24kHz PCM16 Mono)
```

### 3. FastAPI Relay Server (`server.py`)

**Responsibilities:**
- Accept WebSocket connections from browser
- Connect to Azure OpenAI Realtime API
- Relay messages bidirectionally (stateless)
- Forward interruption events
- Serve static files

**Key Functions:**
```python
async def relay_browser_to_azure():
    # Forward user audio and events to Azure
    
async def relay_azure_to_browser():
    # Forward AI responses and events to browser
    # CRITICAL: Detect and forward speech_started events
    
def get_session_config():
    # Configure Azure session with:
    # - System instructions (GXS persona)
    # - Audio formats (PCM16)
    # - VAD settings
```

**Concurrency Model:**
- Two async tasks run concurrently:
  1. `relay_browser_to_azure`: Receives from browser, sends to Azure
  2. `relay_azure_to_browser`: Receives from Azure, sends to browser
- Tasks are cancelled when either completes (disconnect)

### 4. Azure OpenAI Integration

**Session Configuration:**
```json
{
  "type": "session.update",
  "session": {
    "modalities": ["text", "audio"],
    "voice": "shimmer",
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.6,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 600,
      "create_response": true
    }
  }
}
```

**VAD Parameters:**
- `threshold: 0.6`: Sensitivity for detecting speech (0.0-1.0)
- `prefix_padding_ms: 300`: Include 300ms before detected speech
- `silence_duration_ms: 600`: 600ms of silence ends turn
- `create_response: true`: Auto-generate response after user stops

---

## Data Flow

### Conversation Initiation Flow

```
1. User clicks "Start Call"
   │
   ├─> Browser: Request microphone access
   │
   ├─> Browser: Create AudioContext (48kHz)
   │
   ├─> Browser: Load AudioWorklet module
   │
   ├─> Browser: Connect mic → AudioWorklet → WebSocket
   │
   ├─> Server: Accept WebSocket connection
   │
   ├─> Server: Connect to Azure OpenAI
   │
   ├─> Server: Send session configuration
   │
   └─> UI: Display "Connected" status
```

### Audio Capture Flow (User Speaking)

```
Microphone (48kHz Stereo Float32)
   │
   ├─> AudioWorklet: Stereo to Mono
   │
   ├─> AudioWorklet: Linear Interpolation (48kHz → 24kHz)
   │
   ├─> AudioWorklet: Float32 to PCM16
   │
   ├─> WebSocket: Send as base64 in JSON
   │   {
   │     "type": "input_audio_buffer.append",
   │     "audio": "<base64_pcm16_data>"
   │   }
   │
   ├─> Server: Relay to Azure (pass-through)
   │
   ├─> Azure: Server VAD detects speech
   │
   ├─> Azure: Accumulate audio buffer
   │
   └─> Azure: On silence, transcribe and generate response
```

### Audio Playback Flow (AI Speaking)

```
Azure: Generate audio response (PCM16 24kHz)
   │
   ├─> Server: Receive binary audio chunks
   │
   ├─> Server: Relay to browser (pass-through)
   │
   ├─> Browser: Add to audioQueue[]
   │
   ├─> Browser: If not playing, start playback
   │
   ├─> Browser: Convert PCM16 to Float32
   │
   ├─> Browser: Create AudioBuffer (24kHz)
   │
   ├─> Browser: Play via AudioContext
   │
   └─> Browser: On chunk end, play next in queue
```

### Interruption Flow (Barge-In)

```
Azure: Detect speech_started (Server VAD)
   │
   ├─> Azure: Send event
   │   {
   │     "type": "input_audio_buffer.speech_started"
   │   }
   │
   ├─> Server: Forward immediately to browser
   │
   ├─> Browser: Receive speech_started event
   │
   ├─> Browser: CRITICAL - Flush audioQueue = []
   │
   ├─> Browser: Stop current playback
   │
   └─> UI: Log "User speaking - bot interrupted"
```

---

## Technical Decisions

### 1. Why WebSocket Relay (not REST)?

**Decision:** Use stateless WebSocket pass-through relay

**Rationale:**
- **Lowest Latency**: No server-side processing or buffering
- **Simplicity**: Server doesn't need to understand audio
- **Scalability**: Stateless design allows horizontal scaling
- **Reliability**: Fewer points of failure

**Alternatives Considered:**
- ❌ Server-side transcoding: Adds 50-100ms latency
- ❌ REST with polling: Too slow for real-time audio
- ❌ Server-side audio processing: Unnecessary complexity

### 2. Why Linear Interpolation?

**Decision:** Use linear interpolation for resampling (not decimation)

**Rationale:**
- **Audio Quality**: Prevents aliasing and artifacts
- **Simplicity**: Easy to implement and understand
- **Performance**: Fast enough for real-time (O(n))
- **Industry Standard**: Common in professional DSP

**Math Comparison:**
```
Simple Decimation (BAD):
  Input:  [0, 1, 2, 3, 4, 5, 6, 7]  (48kHz)
  Output: [0, 2, 4, 6]              (24kHz) - just drop samples
  Problem: Aliasing, harsh sound

Linear Interpolation (GOOD):
  Input:  [0, 1, 2, 3, 4, 5, 6, 7]
  Output: [0, 1.5, 3, 4.5]          - smooth transition
  Benefit: Natural sound, no artifacts
```

### 3. Why Server VAD (not Client VAD)?

**Decision:** Use Azure's Server VAD, not client-side detection

**Rationale:**
- **Accuracy**: Azure's VAD is highly optimized
- **Consistency**: Same VAD for input detection and turn-taking
- **Simplicity**: No need for client-side ML model
- **Latency**: VAD happens at same location as transcription

**Tradeoff:**
- Network latency for VAD detection (~50-100ms)
- Acceptable for our use case

### 4. Why Audio Queue with Flushing?

**Decision:** Maintain client-side audio playback queue with interruption flushing

**Rationale:**
- **Smooth Playback**: Queue prevents gaps between chunks
- **Instant Interruption**: Flushing enables true barge-in
- **User Experience**: Natural conversation flow

**Implementation:**
```javascript
// Add to queue
this.audioQueue.push(audioChunk);

// On interruption
this.audioQueue = [];  // Instant silence
```

### 5. Why PCM16 (not Opus or AAC)?

**Decision:** Use PCM16 throughout pipeline (no compression)

**Rationale:**
- **Azure Requirement**: Realtime API expects PCM16
- **Zero Latency**: No encode/decode overhead
- **Simplicity**: No codec dependencies
- **Quality**: Lossless audio

**Bandwidth:**
- PCM16 24kHz Mono: ~48 KB/s
- Acceptable for modern internet connections

---

## Performance Optimization

### Latency Budget

Target: < 500ms end-to-end

```
Component                    Latency      Optimization
────────────────────────────────────────────────────────
Microphone Capture           10-20ms     (Hardware)
AudioWorklet Processing      5-10ms      Linear interpolation (O(n))
WebSocket Send              10-30ms      Binary transfer, compression
Network (Browser→Server)     20-50ms      (Geographic proximity)
Server Relay                 1-5ms       Pass-through, no processing
Network (Server→Azure)       20-50ms      Azure region selection
Azure VAD Detection          50-100ms     (Azure processing)
Azure GPT-4o Processing      100-200ms    (Model inference)
Azure Audio Generation       50-100ms     (TTS synthesis)
Network (Azure→Server)       20-50ms      (Return path)
Server Relay                 1-5ms       Pass-through
Network (Server→Browser)     20-50ms      (Return path)
Audio Playback Queue         0-50ms      Immediate on first chunk
────────────────────────────────────────────────────────
TOTAL                        ~307-725ms   
TARGET                       < 500ms      ✓ (in optimal conditions)
```

### Optimization Techniques

1. **Zero-Copy Transfers**
   ```javascript
   // Transfer ArrayBuffer ownership (no copy)
   this.port.postMessage(
     { type: 'audioData', data: buffer },
     [buffer]  // Transferable
   );
   ```

2. **Chunked Processing**
   - AudioWorklet processes 128 samples at a time
   - Send chunks of 4800 samples (200ms) to balance latency vs overhead

3. **Parallel Relay Tasks**
   ```python
   # Two async tasks running concurrently
   await asyncio.wait([
     relay_browser_to_azure(),
     relay_azure_to_browser()
   ], return_when=FIRST_COMPLETED)
   ```

4. **Stateless Server**
   - No session storage
   - No audio buffering
   - Enables horizontal scaling

---

## Security Considerations

### 1. Authentication & Authorization

**Current Implementation:**
- API key stored in `.env` (server-side only)
- Browser never sees Azure credentials

**Production Recommendations:**
- Add user authentication (OAuth, JWT)
- Implement rate limiting per user
- Add session timeouts

### 2. Data Privacy

**Sensitive Data:**
- Voice recordings contain PII
- Conversation transcripts include financial info

**Mitigations:**
- HTTPS/WSS encryption in transit
- No server-side storage (stateless)
- Encourage Azure data residency settings
- GDPR compliance through Azure's DPA

### 3. CORS Protection

```python
allow_origins=[
  "http://localhost:8000",
  "https://yourdomain.com"
]
```

**Production:**
- Restrict to production domain only
- Enable credentials for authenticated sessions

### 4. Input Validation

**Current:**
- WebSocket message size limits (FastAPI default: 16MB)
- Binary audio validation (ArrayBuffer type check)

**Future Enhancements:**
- Audio duration limits (prevent abuse)
- Format validation (ensure PCM16)
- Malicious payload detection

### 5. Compliance

**Regulatory Requirements:**
- **MAS Guidelines** (Singapore): Voice recording consent
- **PDPA** (Singapore): Personal data protection
- **TCPA** (US): Automated call regulations

**Implementation:**
- System instructions include consent notice
- User must proceed to agree
- Transcript download for record-keeping

---

## Scalability Considerations

### Horizontal Scaling

**Stateless Design Benefits:**
- Each WebSocket connection is independent
- No shared state between requests
- Can run multiple server instances behind load balancer

**Load Balancer Configuration:**
```
        ┌─> Server Instance 1
Client ─┤
        └─> Server Instance 2
```

**Requirements:**
- Sticky sessions NOT needed (stateless)
- WebSocket support in load balancer
- Health check endpoint: `/health`

### Vertical Scaling

**Resource Usage per Connection:**
- CPU: Minimal (relay only, no processing)
- Memory: ~1-5 MB per active connection
- Network: ~48 KB/s per connection (PCM16 24kHz)

**Capacity Estimation:**
- 1 vCPU: ~100-500 concurrent connections
- Limited by network bandwidth, not CPU

### Monitoring

**Key Metrics:**
- WebSocket connection count
- Message relay latency
- Error rate by type
- Azure API response times

**Recommended Tools:**
- Prometheus + Grafana
- Azure Monitor integration
- Custom logging with correlation IDs

---

## Future Enhancements

### 1. Advanced Audio Processing
- Noise suppression (Krisp, RNNoise)
- Acoustic echo cancellation (AEC)
- Automatic Gain Control (AGC)

### 2. Multi-Language Support
- Detect user language automatically
- Switch system instructions dynamically
- Support Mandarin, Malay, Tamil

### 3. Sentiment Analysis
- Detect customer frustration
- Escalate to human agent if needed
- Adjust tone dynamically

### 4. Analytics Dashboard
- Conversation success rate
- Average call duration
- Payment commitment tracking
- Agent performance metrics

### 5. Integration
- CRM integration (Salesforce, HubSpot)
- Payment gateway API
- SMS/Email follow-up automation

---

## Conclusion

Vernac's architecture prioritizes **simplicity, latency, and reliability** through:
- Stateless relay design
- High-quality DSP with linear interpolation
- Server VAD with instant client-side interruption
- Zero server-side audio processing

This design achieves sub-500ms latency in optimal conditions while maintaining production-ready code quality, security, and scalability.
