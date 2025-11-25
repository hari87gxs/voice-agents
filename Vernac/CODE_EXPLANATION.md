# Code Explanation - Vernac Voice Agent

This document provides a detailed walkthrough of the codebase, explaining the purpose and implementation of each component.

## Table of Contents
1. [Project Structure](#project-structure)
2. [Server Implementation (server.py)](#server-implementation-serverpy)
3. [AudioWorklet Processor (audio-processor.js)](#audioworklet-processor-audio-processorjs)
4. [Client Implementation (client.js)](#client-implementation-clientjs)
5. [Frontend UI (index.html)](#frontend-ui-indexhtml)
6. [Configuration Files](#configuration-files)

---

## Project Structure

```
Vernac/
├── server.py                 # FastAPI WebSocket relay server
├── client.js                 # Browser client with WebSocket and audio handling
├── audio-processor.js        # AudioWorklet for DSP resampling
├── index.html                # User interface
├── requirements.txt          # Python dependencies
├── package.json              # Project metadata
├── .env.example              # Environment configuration template
├── .gitignore               # Git ignore rules
├── README.md                # Main documentation
├── ARCHITECTURE.md          # System architecture
├── CODE_EXPLANATION.md      # This file
└── test_e2e.py             # End-to-end tests
```

---

## Server Implementation (server.py)

### Overview
The server acts as a **stateless relay** between the browser and Azure OpenAI. It doesn't process audio, ensuring minimal latency.

### Imports and Configuration

```python
import os
import asyncio
import json
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import websockets
import uvicorn
```

**Key Libraries:**
- `fastapi`: Modern async web framework
- `websockets`: WebSocket client for Azure connection
- `uvicorn`: ASGI server for FastAPI
- `python-dotenv`: Environment variable management

### Environment Variables

```python
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
```

**Purpose:** Keep sensitive credentials out of code. These are loaded from `.env` file.

### System Instructions

```python
SYSTEM_INSTRUCTIONS = """You are a professional debt collection agent..."""
```

**What This Does:**
- Defines the AI's persona and behavior
- Implements GXS Bank's collection flow
- Includes compliance requirements (legal disclaimers)
- Specifies Singlish tone ("Ah," "Okay," "Right")

**Key Sections:**
1. **Opening**: Compliance notice + account status
2. **Waterfall Negotiation**: 3 days → 7 days → credit warning
3. **Edge Cases**: Financial difficulty, partial payment, disputes

### Session Configuration

```python
def get_session_config() -> dict:
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": SYSTEM_INSTRUCTIONS,
            "voice": "shimmer",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.6,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 600,
                "create_response": True
            }
        }
    }
```

**Critical Parameters:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `modalities` | `["text", "audio"]` | Enable both text and voice |
| `voice` | `"shimmer"` | Azure's voice selection |
| `input_audio_format` | `"pcm16"` | Expect PCM16 from browser |
| `output_audio_format` | `"pcm16"` | Send PCM16 to browser |
| `threshold` | `0.6` | VAD sensitivity (0.0-1.0) |
| `prefix_padding_ms` | `300` | Include 300ms before speech |
| `silence_duration_ms` | `600` | End turn after 600ms silence |
| `create_response` | `True` | Auto-respond after turn |

### Relay Functions

#### Browser → Azure Relay

```python
async def relay_browser_to_azure(browser_ws: WebSocket, azure_ws: websockets.WebSocketClientProtocol):
    try:
        while True:
            message = await browser_ws.receive()
            
            if "text" in message:
                # JSON message (events)
                await azure_ws.send(message["text"])
                
            elif "bytes" in message:
                # Binary audio data
                await azure_ws.send(message["bytes"])
    except WebSocketDisconnect:
        logger.info("Browser disconnected")
```

**How It Works:**
1. Wait for message from browser
2. Check if text (JSON) or bytes (audio)
3. Forward to Azure without modification
4. Loop until disconnect

**Why Pass-Through?**
- Zero latency overhead
- No audio decoding/encoding
- Simple and reliable

#### Azure → Browser Relay

```python
async def relay_azure_to_browser(azure_ws: websockets.WebSocketClientProtocol, browser_ws: WebSocket):
    try:
        async for message in azure_ws:
            if isinstance(message, str):
                # JSON - parse to check for interruption events
                msg_data = json.loads(message)
                event_type = msg_data.get("type", "")
                
                # CRITICAL: Forward speech_started for barge-in
                if event_type == "input_audio_buffer.speech_started":
                    logger.info("🎤 User started speaking - triggering barge-in")
                
                await browser_ws.send_text(message)
                
            elif isinstance(message, bytes):
                # Binary audio
                await browser_ws.send_bytes(message)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Azure connection closed")
```

**Critical Feature: Interruption Detection**
```python
if event_type == "input_audio_buffer.speech_started":
    logger.info("🎤 User started speaking - triggering barge-in")
```

This event is **immediately forwarded** to the browser, which then flushes its audio queue to stop the bot from talking.

### WebSocket Endpoint

```python
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Connect to Azure
    azure_ws = await websockets.connect(
        azure_url,
        additional_headers={"api-key": AZURE_API_KEY}
    )
    
    # Send session config
    await azure_ws.send(json.dumps(get_session_config()))
    
    # Start bidirectional relay
    browser_to_azure_task = asyncio.create_task(
        relay_browser_to_azure(websocket, azure_ws)
    )
    azure_to_browser_task = asyncio.create_task(
        relay_azure_to_browser(azure_ws, websocket)
    )
    
    # Wait for either to complete (disconnect)
    done, pending = await asyncio.wait(
        [browser_to_azure_task, azure_to_browser_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Cancel remaining task
    for task in pending:
        task.cancel()
```

**Concurrency Model:**
- Two tasks run in parallel
- If either completes (disconnect), cancel the other
- Ensures clean shutdown

### Static File Serving

```python
@app.get("/")
async def get_index():
    return FileResponse("index.html")

@app.get("/client.js")
async def get_client_js():
    return FileResponse("client.js", media_type="application/javascript")
```

**Why Not StaticFiles Middleware?**
- More control over MIME types
- Explicit routing for better security
- Only serve necessary files

---

## AudioWorklet Processor (audio-processor.js)

### Overview
The AudioWorklet runs on a **separate thread** from the main UI, enabling real-time audio processing without blocking.

### Class Structure

```javascript
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        this.targetSampleRate = 24000;
        this.sourceSampleRate = 48000;
        this.resampleRatio = 0.5;  // 24000/48000
        this.sourcePosition = 0;
        this.outputBuffer = [];
        this.chunkSize = 4800;  // ~200ms at 24kHz
    }
}
```

**Key State Variables:**

| Variable | Purpose |
|----------|---------|
| `targetSampleRate` | Azure's required rate (24kHz) |
| `sourceSampleRate` | Browser's capture rate (48kHz) |
| `resampleRatio` | Conversion factor (0.5 = half) |
| `sourcePosition` | Track position for continuity |
| `outputBuffer` | Accumulate samples before sending |

### Main Processing Loop

```javascript
process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    
    // Get mono input (average stereo if needed)
    const monoInput = this.stereoToMono(input);
    
    // Resample with linear interpolation
    const resampled = this.resampleWithLinearInterpolation(monoInput);
    
    // Convert Float32 to PCM16
    const pcm16 = this.floatToPCM16(resampled);
    
    // Buffer and send chunks
    this.outputBuffer.push(...pcm16);
    while (this.outputBuffer.length >= this.chunkSize) {
        const chunk = this.outputBuffer.splice(0, this.chunkSize);
        this.port.postMessage({
            type: 'audioData',
            data: new Int16Array(chunk).buffer
        }, [new Int16Array(chunk).buffer]);
    }
    
    return true;
}
```

**Processing Steps:**
1. **Stereo → Mono**: Average left and right channels
2. **Resample**: 48kHz → 24kHz with interpolation
3. **Convert Format**: Float32 → PCM16
4. **Buffer**: Accumulate samples
5. **Send**: Transfer chunks to main thread

### Linear Interpolation Algorithm

```javascript
resampleWithLinearInterpolation(input) {
    const outputLength = Math.floor(input.length * this.resampleRatio);
    const output = new Float32Array(outputLength);
    const step = 1.0 / this.resampleRatio;  // 2.0 for 48→24kHz
    
    for (let i = 0; i < outputLength; i++) {
        // Calculate fractional position in source
        const position = this.sourcePosition + (i * step);
        const index = Math.floor(position);
        const fraction = position - index;
        
        if (index + 1 < input.length) {
            // LINEAR INTERPOLATION
            const sample0 = input[index];
            const sample1 = input[index + 1];
            output[i] = sample0 + (sample1 - sample0) * fraction;
        } else {
            output[i] = input[index] || 0;
        }
    }
    
    return output;
}
```

**Mathematical Breakdown:**

Given: 48kHz → 24kHz (ratio = 0.5)

Example: Generate 4 output samples from 8 input samples
```
Input:  [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]  (48kHz)

Output sample 0:
  position = 0.0 * 2.0 = 0.0
  index = 0, fraction = 0.0
  value = input[0] + (input[1] - input[0]) * 0.0 = 0.0

Output sample 1:
  position = 1.0 * 2.0 = 2.0
  index = 2, fraction = 0.0
  value = input[2] + (input[3] - input[2]) * 0.0 = 0.2

Output sample 2:
  position = 2.0 * 2.0 = 4.0
  index = 4, fraction = 0.0
  value = input[4] = 0.4

Output sample 3:
  position = 3.0 * 2.0 = 6.0
  index = 6, fraction = 0.0
  value = input[6] = 0.6

Output: [0.0, 0.2, 0.4, 0.6]  (24kHz)
```

**With Fractional Positions:**
```
If ratio = 0.6 (non-integer)
position = 1.0 * (1/0.6) = 1.667

index = 1, fraction = 0.667

value = input[1] + (input[2] - input[1]) * 0.667
      = 0.1 + (0.2 - 0.1) * 0.667
      = 0.1 + 0.0667
      = 0.1667
```

This creates a **smooth transition** between samples, preventing audio artifacts.

### Float32 to PCM16 Conversion

```javascript
floatToPCM16(floatSamples) {
    const pcm16 = [];
    
    for (let i = 0; i < floatSamples.length; i++) {
        // Scale from [-1.0, 1.0] to [-32768, 32767]
        let val = floatSamples[i] * 32768;
        
        // Clamp and round
        val = Math.max(-32768, Math.min(32767, Math.round(val)));
        
        pcm16.push(val);
    }
    
    return pcm16;
}
```

**Conversion Formula:**
```
Float32 range: -1.0 to +1.0
PCM16 range:   -32768 to +32767

PCM16 = clamp(round(Float32 * 32768), -32768, 32767)
```

**Examples:**
- `0.0` → `0`
- `1.0` → `32768` → clamped to `32767`
- `-1.0` → `-32768`
- `0.5` → `16384`
- `-0.5` → `-16384`

---

## Client Implementation (client.js)

### Class Structure

```javascript
class VernacVoiceClient {
    constructor() {
        this.ws = null;
        this.audioContext = null;
        this.micStream = null;
        this.audioWorkletNode = null;
        this.audioQueue = [];
        this.transcript = [];
        // ... UI elements
    }
}
```

### Starting a Call

```javascript
async startCall() {
    // 1. Create AudioContext
    this.audioContext = new AudioContext({ sampleRate: 48000 });
    
    // 2. Request microphone
    this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            channelCount: 1,
            sampleRate: 48000,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        }
    });
    
    // 3. Load AudioWorklet
    await this.audioContext.audioWorklet.addModule('audio-processor.js');
    
    // 4. Create AudioWorklet node
    this.audioWorkletNode = new AudioWorkletNode(
        this.audioContext,
        'pcm-processor'
    );
    
    // 5. Connect pipeline
    const source = this.audioContext.createMediaStreamSource(this.micStream);
    source.connect(this.audioWorkletNode);
    
    // 6. Handle processed audio
    this.audioWorkletNode.port.onmessage = (event) => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(this.createAudioMessage(event.data.data));
        }
    };
    
    // 7. Connect WebSocket
    await this.connectWebSocket();
}
```

**Pipeline Flow:**
```
Microphone
    ↓
MediaStreamSource (Web Audio API)
    ↓
AudioWorkletNode (PCMProcessor)
    ↓
Port Message (ArrayBuffer)
    ↓
WebSocket Send (JSON with base64)
```

### WebSocket Message Handling

```javascript
handleWebSocketMessage(event) {
    if (typeof event.data === 'string') {
        // JSON message
        const message = JSON.parse(event.data);
        this.handleServerEvent(message);
    } else if (event.data instanceof ArrayBuffer) {
        // Binary audio
        this.handleAudioResponse(event.data);
    }
}
```

**Message Types:**
- **String**: Events, transcripts, control messages (JSON)
- **ArrayBuffer**: Audio data (PCM16)

### Critical: Barge-In Handling

```javascript
handleServerEvent(message) {
    const eventType = message.type;
    
    switch (eventType) {
        case 'input_audio_buffer.speech_started':
            // USER STARTED SPEAKING - INTERRUPT BOT
            this.log('🎤 User speaking detected - interrupting bot', 'info');
            this.handleBargeIn();
            break;
        // ... other events
    }
}

handleBargeIn() {
    // CRITICAL: Clear audio queue immediately
    this.audioQueue = [];
    this.isPlaying = false;
    
    // Stop current playback with brief silence
    const silenceBuffer = this.audioContext.createBuffer(
        1,
        this.audioContext.sampleRate * 0.1,
        this.audioContext.sampleRate
    );
    
    const source = this.audioContext.createBufferSource();
    source.buffer = silenceBuffer;
    source.connect(this.audioContext.destination);
    source.start();
    
    this.log('✓ Audio queue flushed - bot interrupted', 'success');
}
```

**Why This Works:**
1. Azure detects user speech (Server VAD)
2. Server forwards `speech_started` event
3. Client receives event **while bot is still talking**
4. Client **immediately clears** `audioQueue[]`
5. No more bot audio plays
6. User can speak without bot talking over them

**Timing Diagram:**
```
Time    Bot Audio Queue    User Speech    Action
────────────────────────────────────────────────────
0ms     [chunk1, chunk2]   Silent         Bot talking
100ms   [chunk1, chunk2]   Silent         Bot talking
200ms   [chunk1, chunk2]   STARTS         Azure VAD detects
250ms   [chunk1, chunk2]   Speaking       Event sent to server
300ms   []                 Speaking       Queue flushed! ← BARGE-IN
350ms   []                 Speaking       User has floor
```

### Audio Playback Queue

```javascript
handleAudioResponse(audioData) {
    // Add to queue
    this.audioQueue.push(audioData);
    
    // Start playback if not already playing
    if (!this.isPlaying) {
        this.playNextAudioChunk();
    }
}

async playNextAudioChunk() {
    if (this.audioQueue.length === 0) {
        this.isPlaying = false;
        return;
    }
    
    this.isPlaying = true;
    const audioData = this.audioQueue.shift();
    
    // Convert PCM16 to AudioBuffer
    const audioBuffer = await this.pcm16ToAudioBuffer(audioData);
    
    // Play
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);
    source.onended = () => this.playNextAudioChunk();
    source.start();
}
```

**Queue Management:**
- Audio chunks arrive from Azure
- Added to queue in order
- Played sequentially (no gaps)
- On interruption, queue is flushed

### PCM16 to AudioBuffer Conversion

```javascript
async pcm16ToAudioBuffer(pcm16Data) {
    const int16Array = new Int16Array(pcm16Data);
    const float32Array = new Float32Array(int16Array.length);
    
    // Convert Int16 to Float32
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
    }
    
    // Create AudioBuffer
    const audioBuffer = this.audioContext.createBuffer(
        1,        // Mono
        float32Array.length,
        24000     // 24kHz
    );
    
    audioBuffer.getChannelData(0).set(float32Array);
    return audioBuffer;
}
```

**Reverse Conversion:**
```
PCM16 range:   -32768 to +32767
Float32 range: -1.0 to +1.0

Float32 = PCM16 / 32768
```

### Transcript Management

```javascript
addToTranscript(role, text) {
    if (!text || text.trim() === '') return;
    
    this.transcript.push({
        role,
        text,
        timestamp: new Date()
    });
    
    this.renderTranscript();
}

renderTranscript() {
    this.transcriptDiv.innerHTML = '';
    
    this.transcript.forEach(item => {
        const div = document.createElement('div');
        div.className = 'transcript-item';
        
        const roleLabel = item.role === 'user' ? 'You' : 'GXS Agent';
        div.innerHTML = `
            <div class="transcript-role ${item.role}">${roleLabel}</div>
            <div class="transcript-text">${this.escapeHtml(item.text)}</div>
        `;
        
        this.transcriptDiv.appendChild(div);
    });
    
    this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
}
```

**Data Structure:**
```javascript
[
  {
    role: 'assistant',
    text: 'Hi, this is an AI message from GXS Bank...',
    timestamp: Date(2025-11-25T10:30:00)
  },
  {
    role: 'user',
    text: 'Yes, I can pay in 3 days',
    timestamp: Date(2025-11-25T10:30:15)
  }
]
```

### Transcript Download

```javascript
downloadTranscript() {
    let content = 'GXS Bank Voice Agent - Conversation Transcript\n';
    content += '='.repeat(50) + '\n\n';
    
    this.transcript.forEach(item => {
        const timestamp = item.timestamp.toLocaleString();
        const role = item.role === 'user' ? 'YOU' : 'GXS AGENT';
        content += `[${timestamp}] ${role}:\n${item.text}\n\n`;
    });
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vernac-transcript-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
```

**Output Format:**
```
GXS Bank Voice Agent - Conversation Transcript
==================================================

[11/25/2025, 10:30:00 AM] GXS AGENT:
Hi, this is an AI message from GXS Bank regarding your FlexiLoan account...

[11/25/2025, 10:30:15 AM] YOU:
Yes, I can pay in 3 days

[11/25/2025, 10:30:20 AM] GXS AGENT:
That's great! You can make the payment through the GXS Bank app...
```

---

## Frontend UI (index.html)

### Layout Structure

```html
<div class="container">
    <div class="header">
        <h1>🎙️ Vernac Voice Agent</h1>
        <p>GXS Bank - Voice-to-Voice Debt Collection</p>
    </div>
    
    <div class="content">
        <div class="status">Ready to connect</div>
        
        <div class="controls">
            <button class="btn btn-start">Start Call</button>
            <button class="btn btn-end">End Call</button>
        </div>
        
        <div class="transcript-section">
            <h2>Conversation Transcript</h2>
            <button class="btn-download">📥 Download</button>
            <div class="transcript"></div>
        </div>
        
        <div class="log"></div>
    </div>
</div>
```

### Styling Highlights

**Gradient Background:**
```css
body {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
```

**Button Hover Effects:**
```css
.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}
```

**Status Indicator Animation:**
```css
.indicator {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

**Scrollable Transcript:**
```css
.transcript {
    max-height: 400px;
    overflow-y: auto;
}

.transcript::-webkit-scrollbar {
    width: 8px;
}
```

---

## Configuration Files

### .env.example

```env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-realtime-preview

HOST=0.0.0.0
PORT=8000

ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

**Usage:**
```bash
cp .env.example .env
# Edit .env with real credentials
```

### requirements.txt

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-dotenv==1.0.0
aiohttp==3.9.1
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

## Key Algorithms Summary

### 1. Linear Interpolation Resampling

**Input:** Float32 audio at 48kHz  
**Output:** Float32 audio at 24kHz

```
For each output sample i:
    1. position = i * (sourcerate / targetRate)
    2. idx = floor(position)
    3. frac = position - idx
    4. output[i] = input[idx] + (input[idx+1] - input[idx]) * frac
```

### 2. Float32 ↔ PCM16 Conversion

**Float32 → PCM16:**
```
PCM16 = clamp(round(Float32 * 32768), -32768, 32767)
```

**PCM16 → Float32:**
```
Float32 = PCM16 / 32768
```

### 3. Barge-In (Interruption)

**Algorithm:**
```
1. Azure: Detect user speech (Server VAD)
2. Azure: Send speech_started event
3. Server: Forward event immediately (pass-through)
4. Client: Receive event
5. Client: audioQueue = []  ← CRITICAL
6. Client: isPlaying = false
7. Result: Bot stops talking instantly
```

### 4. Audio Playback Queue

**Queue Management:**
```javascript
// Add chunk
audioQueue.push(chunk);
if (!isPlaying) playNext();

// Play chunk
function playNext() {
    if (audioQueue.length === 0) return;
    chunk = audioQueue.shift();
    play(chunk, onEnded: playNext);
}

// Interruption
audioQueue = [];  // Clear all pending
```

---

## Data Formats

### WebSocket Messages

**Audio from Browser to Server:**
```json
{
  "type": "input_audio_buffer.append",
  "audio": "<base64_encoded_pcm16_data>"
}
```

**Audio from Server to Browser:**
```
Binary ArrayBuffer (raw PCM16 bytes)
```

**Events (JSON):**
```json
{
  "type": "input_audio_buffer.speech_started"
}

{
  "type": "conversation.item.input_audio_transcription.completed",
  "transcript": "Yes, I can pay in 3 days"
}

{
  "type": "response.audio_transcript.done",
  "transcript": "That's great! You can make payment..."
}
```

### Audio Specifications

| Property | Value |
|----------|-------|
| **Format** | PCM16 (Linear 16-bit) |
| **Sample Rate** | 24,000 Hz |
| **Channels** | 1 (Mono) |
| **Bit Depth** | 16 bits |
| **Endianness** | Little Endian |
| **Bandwidth** | ~48 KB/s (24000 samples/s × 2 bytes) |

---

## Error Handling

### Server Errors

```python
try:
    # WebSocket operations
except WebSocketDisconnect:
    logger.info("Browser disconnected")
except Exception as e:
    logger.error(f"Error: {e}")
    await websocket.send_text(json.dumps({
        "type": "error",
        "error": {"message": str(e)}
    }))
```

### Client Errors

```javascript
try {
    await this.startCall();
} catch (error) {
    this.log(`Error: ${error.message}`, 'error');
    this.updateStatus(`Error: ${error.message}`, true);
    await this.cleanup();
}
```

### Common Error Scenarios

1. **Microphone Access Denied**
   - Error: `NotAllowedError: Permission denied`
   - Solution: User must grant permission

2. **WebSocket Connection Failed**
   - Error: `WebSocket connection timeout`
   - Solution: Check server is running, firewall rules

3. **Azure API Key Invalid**
   - Error: `401 Unauthorized`
   - Solution: Verify `.env` configuration

4. **AudioWorklet Load Failed**
   - Error: `Failed to fetch`
   - Solution: Check `audio-processor.js` exists and is served correctly

---

## Performance Considerations

### Memory Management

**AudioWorklet:**
- Uses transferable objects (zero-copy)
```javascript
this.port.postMessage(
    { data: buffer },
    [buffer]  // Transfer ownership
);
```

**Client:**
- Limits log to 100 items
```javascript
while (this.logDiv.children.length > 100) {
    this.logDiv.removeChild(this.logDiv.firstChild);
}
```

### Latency Optimization

1. **No Buffering:** Audio sent immediately after processing
2. **Small Chunks:** 200ms chunks balance latency vs overhead
3. **Binary Transfer:** ArrayBuffer is faster than base64
4. **Pass-Through Server:** No audio processing on server

### CPU Usage

**AudioWorklet (Separate Thread):**
- Minimal impact on main thread
- Linear interpolation is O(n)

**Main Thread:**
- WebSocket handling
- UI updates
- Audio playback scheduling

---

## Security Best Practices

### 1. Never Expose API Keys

```python
# ✓ Good
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

# ✗ Bad
AZURE_API_KEY = "sk-1234567890abcdef"  # Hardcoded!
```

### 2. Input Validation

```javascript
// Validate message type
if (typeof event.data === 'string') {
    try {
        JSON.parse(event.data);
    } catch {
        // Invalid JSON, ignore
    }
}
```

### 3. XSS Prevention

```javascript
escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;  // Automatically escapes
    return div.innerHTML;
}
```

### 4. CORS Protection

```python
allow_origins=[
    "http://localhost:8000",
    "https://yourdomain.com"
]
```

---

## Testing Strategies

### Manual Testing Checklist

- [ ] Microphone capture works
- [ ] Audio plays from bot
- [ ] User can interrupt bot (barge-in)
- [ ] Transcript displays correctly
- [ ] Transcript downloads as .txt
- [ ] WebSocket reconnects on disconnect
- [ ] Error messages display properly
- [ ] Works in Chrome, Firefox, Safari, Edge

### Audio Quality Tests

- [ ] No clipping or distortion
- [ ] No gaps between audio chunks
- [ ] Bot stops immediately on interruption
- [ ] Latency < 500ms (optimal conditions)

### Edge Cases

- [ ] Deny microphone permission
- [ ] Disconnect during call
- [ ] Server restart during call
- [ ] Long silence (no timeout)
- [ ] Rapid interruptions

---

## Conclusion

The Vernac codebase demonstrates:

1. **High-Quality DSP**: Linear interpolation for artifact-free resampling
2. **Low Latency**: Stateless relay architecture with no server-side processing
3. **Natural Conversation**: Instant barge-in via audio queue flushing
4. **Production Ready**: Error handling, logging, security best practices
5. **Maintainable**: Clear code structure, comprehensive comments, modular design

Each component is designed with a specific purpose, working together to create a seamless voice AI experience for GXS Bank's debt collection operations.
