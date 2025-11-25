/**
 * Vernac Voice Agent - Client-Side JavaScript
 * 
 * This script handles:
 * 1. WebSocket connection to the relay server
 * 2. Microphone capture and audio processing via AudioWorklet
 * 3. Audio playback with queue management
 * 4. Barge-in (interruption) handling when user starts speaking
 * 5. Transcript display and download
 * 6. UI updates and status logging
 */

class VernacVoiceClient {
    constructor() {
        // WebSocket connection
        this.ws = null;
        // Automatically use wss:// for HTTPS pages, ws:// for HTTP
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.wsUrl = `${wsProtocol}//${window.location.host}/ws/chat`;
        
        // Audio context and nodes
        this.audioContext = null;
        this.micStream = null;
        this.audioWorkletNode = null;
        
        // Audio playback queue for managing bot responses
        this.audioQueue = [];
        this.isPlaying = false;
        
        // Transcript storage
        this.transcript = [];
        
        // State flags
        this.isConnected = false;
        this.isRecording = false;
        
        // UI elements
        this.startBtn = document.getElementById('startBtn');
        this.endBtn = document.getElementById('endBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.statusDiv = document.getElementById('status');
        this.transcriptDiv = document.getElementById('transcript');
        this.logDiv = document.getElementById('log');
        
        // Bind event handlers
        this.startBtn.addEventListener('click', () => this.startCall());
        this.endBtn.addEventListener('click', () => this.endCall());
        this.downloadBtn.addEventListener('click', () => this.downloadTranscript());
    }
    
    /**
     * Start a voice call
     * 1. Initialize microphone
     * 2. Set up AudioWorklet
     * 3. Connect WebSocket
     * 4. Start streaming audio
     */
    async startCall() {
        try {
            this.log('Initializing voice call...', 'info');
            this.updateStatus('Initializing...', false, false);
            
            // Step 1: Initialize Audio Context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 48000, // Browser's native sample rate
            });
            
            this.log(`Audio context created: ${this.audioContext.sampleRate}Hz`, 'success');
            
            // Step 2: Request microphone access
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1, // Mono
                    sampleRate: 48000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });
            
            this.log('Microphone access granted', 'success');
            
            // Step 3: Load AudioWorklet processor
            await this.audioContext.audioWorklet.addModule('audio-processor.js');
            this.log('AudioWorklet processor loaded', 'success');
            
            // Step 4: Create AudioWorklet node
            this.audioWorkletNode = new AudioWorkletNode(
                this.audioContext,
                'pcm-processor'
            );
            
            // Configure the processor with source sample rate
            this.audioWorkletNode.port.postMessage({
                type: 'configure',
                sourceSampleRate: this.audioContext.sampleRate
            });
            
            // Step 5: Connect microphone to AudioWorklet
            const source = this.audioContext.createMediaStreamSource(this.micStream);
            source.connect(this.audioWorkletNode);
            
            this.log('Audio pipeline connected', 'success');
            
            // Step 6: Handle processed audio from AudioWorklet
            this.audioWorkletNode.port.onmessage = (event) => {
                if (event.data.type === 'audioData' && this.ws && this.ws.readyState === WebSocket.OPEN) {
                    // Send PCM16 audio data to server
                    this.ws.send(this.createAudioMessage(event.data.data));
                }
            };
            
            // Step 7: Connect WebSocket
            await this.connectWebSocket();
            
            // Update UI
            this.startBtn.disabled = true;
            this.endBtn.disabled = false;
            this.isRecording = true;
            this.updateStatus('Connected - Speaking with GXS Agent', false, true);
            
        } catch (error) {
            this.log(`Error starting call: ${error.message}`, 'error');
            this.updateStatus(`Error: ${error.message}`, true, false);
            this.cleanup();
        }
    }
    
    /**
     * Connect to WebSocket server
     */
    connectWebSocket() {
        return new Promise((resolve, reject) => {
            this.log('Connecting to WebSocket...', 'info');
            
            this.ws = new WebSocket(this.wsUrl);
            this.ws.binaryType = 'arraybuffer';
            
            this.ws.onopen = () => {
                this.log('WebSocket connected', 'success');
                this.isConnected = true;
                resolve();
            };
            
            this.ws.onmessage = (event) => this.handleWebSocketMessage(event);
            
            this.ws.onerror = (error) => {
                this.log('WebSocket error', 'error');
                reject(error);
            };
            
            this.ws.onclose = () => {
                this.log('WebSocket disconnected', 'info');
                this.isConnected = false;
                if (this.isRecording) {
                    this.endCall();
                }
            };
            
            // Timeout after 10 seconds
            setTimeout(() => {
                if (!this.isConnected) {
                    reject(new Error('WebSocket connection timeout'));
                }
            }, 10000);
        });
    }
    
    /**
     * Handle incoming WebSocket messages
     * @param {MessageEvent} event - WebSocket message event
     */
    handleWebSocketMessage(event) {
        if (typeof event.data === 'string') {
            // JSON message (events, transcripts, etc.)
            try {
                const message = JSON.parse(event.data);
                this.handleServerEvent(message);
            } catch (error) {
                this.log(`Error parsing message: ${error.message}`, 'error');
            }
        } else if (event.data instanceof ArrayBuffer) {
            // Binary audio data from Azure
            this.handleAudioResponse(event.data);
        }
    }
    
    /**
     * Handle server events (JSON messages)
     * @param {Object} message - Parsed JSON message
     */
    handleServerEvent(message) {
        const eventType = message.type;
        
        // Log important events
        if (eventType !== 'response.audio.delta') { // Don't spam logs with audio deltas
            this.log(`Event: ${eventType}`, 'info');
        }
        
        switch (eventType) {
            case 'session.created':
                this.log('Session created with Azure OpenAI', 'success');
                break;
                
            case 'session.updated':
                this.log('Session configured successfully', 'success');
                break;
                
            case 'input_audio_buffer.speech_started':
                // CRITICAL: User started speaking - trigger barge-in
                this.log('🎤 User speaking detected - interrupting bot', 'info');
                this.handleBargeIn();
                break;
                
            case 'input_audio_buffer.speech_stopped':
                this.log('User stopped speaking', 'info');
                break;
                
            case 'conversation.item.created':
                // New conversation item (user input or assistant response)
                if (message.item) {
                    this.handleConversationItem(message.item);
                }
                break;
                
            case 'response.audio.delta':
                // Audio chunk from assistant (base64-encoded PCM16)
                if (message.delta) {
                    this.handleAudioDelta(message.delta);
                }
                break;
                
            case 'response.audio_transcript.delta':
                // Partial transcript from assistant
                if (message.delta) {
                    this.updateAssistantTranscript(message.delta);
                }
                break;
                
            case 'response.audio_transcript.done':
                // Complete transcript from assistant
                if (message.transcript) {
                    this.addToTranscript('assistant', message.transcript);
                }
                break;
                
            case 'conversation.item.input_audio_transcription.completed':
                // User's speech transcription
                if (message.transcript) {
                    this.addToTranscript('user', message.transcript);
                }
                break;
                
            case 'response.done':
                this.log('Response completed', 'success');
                break;
                
            case 'error':
                this.log(`Error: ${message.error?.message || 'Unknown error'}`, 'error');
                this.updateStatus(`Error: ${message.error?.message}`, true, false);
                break;
        }
    }
    
    /**
     * Handle barge-in (user interruption)
     * CRITICAL: Immediately flush audio playback queue to stop bot from talking
     */
    handleBargeIn() {
        // Clear the audio queue to stop bot immediately
        this.audioQueue = [];
        this.isPlaying = false;
        
        // Stop any currently playing audio
        if (this.audioContext) {
            // Create a brief silence to "flush" the audio pipeline
            const silenceBuffer = this.audioContext.createBuffer(
                1,
                this.audioContext.sampleRate * 0.1, // 100ms of silence
                this.audioContext.sampleRate
            );
            
            const source = this.audioContext.createBufferSource();
            source.buffer = silenceBuffer;
            source.connect(this.audioContext.destination);
            source.start();
        }
        
        this.log('✓ Audio queue flushed - bot interrupted', 'success');
    }
    
    /**
     * Handle audio delta from Azure (base64-encoded PCM16)
     * @param {string} base64Audio - Base64-encoded PCM16 audio data
     */
    handleAudioDelta(base64Audio) {
        // Decode base64 to binary
        const binaryString = atob(base64Audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // Convert to ArrayBuffer and add to queue
        this.handleAudioResponse(bytes.buffer);
    }
    
    /**
     * Handle incoming audio from Azure (bot response)
     * @param {ArrayBuffer} audioData - PCM16 audio data
     */
    handleAudioResponse(audioData) {
        // Add to playback queue
        this.audioQueue.push(audioData);
        
        // Start playback if not already playing
        if (!this.isPlaying) {
            this.playNextAudioChunk();
        }
    }
    
    /**
     * Play the next audio chunk from the queue
     */
    async playNextAudioChunk() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }
        
        this.isPlaying = true;
        const audioData = this.audioQueue.shift();
        
        try {
            const audioBuffer = await this.pcm16ToAudioBuffer(audioData);
            
            // Apply crossfade to reduce clicks/pops between chunks
            const channelData = audioBuffer.getChannelData(0);
            const fadeLength = Math.min(50, channelData.length); // 50 samples fade
            
            // Fade in at the start
            for (let i = 0; i < fadeLength; i++) {
                const fadeFactor = Math.sin((i / fadeLength) * (Math.PI / 2)); // Sine curve
                channelData[i] *= fadeFactor;
            }
            
            // Fade out at the end
            for (let i = 0; i < fadeLength; i++) {
                const idx = channelData.length - fadeLength + i;
                const fadeFactor = Math.cos((i / fadeLength) * (Math.PI / 2)); // Sine curve
                channelData[idx] *= fadeFactor;
            }
            
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            source.start();
            
            source.onended = () => {
                this.playNextAudioChunk();
            };
        } catch (error) {
            this.log(`Error playing audio: ${error.message}`, 'error');
            this.isPlaying = false;
        }
    }
    
    /**
     * Convert PCM16 data to AudioBuffer for playback
     * @param {ArrayBuffer} pcm16Data - PCM16 audio data
     * @returns {AudioBuffer} - Audio buffer ready for playback
     */
    async pcm16ToAudioBuffer(pcm16Data) {
        // PCM16 is Int16 (2 bytes per sample)
        const int16Array = new Int16Array(pcm16Data);
        
        // Convert Int16 to Float32 for Web Audio API
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            // Convert from [-32768, 32767] to [-1.0, 1.0]
            float32Array[i] = int16Array[i] / 32768.0;
        }
        
        // Apply very short fade-in/out to prevent clicks between chunks
        const fadeLength = Math.min(50, Math.floor(float32Array.length / 20)); // 50 samples or 5% of chunk
        
        // Fade in at start
        for (let i = 0; i < fadeLength; i++) {
            const gain = Math.sin((i / fadeLength) * Math.PI / 2); // Smooth sine curve
            float32Array[i] *= gain;
        }
        
        // Fade out at end  
        for (let i = 0; i < fadeLength; i++) {
            const gain = Math.sin(((fadeLength - i) / fadeLength) * Math.PI / 2);
            float32Array[float32Array.length - 1 - i] *= gain;
        }
        
        // Create AudioBuffer at 24kHz (Azure's output rate)
        const audioBuffer = this.audioContext.createBuffer(
            1, // Mono
            float32Array.length,
            24000 // 24kHz sample rate
        );
        
        // Copy data to buffer
        audioBuffer.getChannelData(0).set(float32Array);
        
        return audioBuffer;
    }
    
    /**
     * Handle conversation items (user input or assistant response)
     * @param {Object} item - Conversation item
     */
    handleConversationItem(item) {
        const role = item.role;
        const content = item.content;
        
        if (content && Array.isArray(content)) {
            content.forEach(part => {
                if (part.type === 'input_audio' || part.type === 'audio') {
                    // Audio content - will be transcribed separately
                    this.log(`${role} sent audio`, 'info');
                } else if (part.type === 'text' && part.text) {
                    this.addToTranscript(role, part.text);
                }
            });
        }
    }
    
    /**
     * Update assistant transcript (streaming)
     * @param {string} delta - Partial transcript
     */
    updateAssistantTranscript(delta) {
        // For now, we'll wait for the complete transcript
        // You could implement streaming display here
    }
    
    /**
     * Add text to transcript
     * @param {string} role - 'user' or 'assistant'
     * @param {string} text - Transcript text
     */
    addToTranscript(role, text) {
        if (!text || text.trim() === '') return;
        
        this.transcript.push({ role, text, timestamp: new Date() });
        this.renderTranscript();
        this.downloadBtn.disabled = false;
    }
    
    /**
     * Render transcript to UI
     */
    renderTranscript() {
        this.transcriptDiv.innerHTML = '';
        
        this.transcript.forEach(item => {
            const div = document.createElement('div');
            div.className = 'transcript-item';
            
            const roleLabel = item.role === 'user' ? 'You' : 'Newton';
            const roleClass = item.role === 'user' ? 'user' : 'assistant';
            
            div.innerHTML = `
                <div class="transcript-role ${roleClass}">${roleLabel}</div>
                <div class="transcript-text">${this.escapeHtml(item.text)}</div>
            `;
            
            this.transcriptDiv.appendChild(div);
        });
        
        // Auto-scroll to bottom
        this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
    }
    
    /**
     * Download transcript as text file
     */
    downloadTranscript() {
        if (this.transcript.length === 0) {
            alert('No transcript to download');
            return;
        }
        
        let content = 'Newton Science Professor - Conversation Transcript\n';
        content += '='.repeat(50) + '\n\n';
        
        this.transcript.forEach(item => {
            const timestamp = item.timestamp.toLocaleString();
            const role = item.role === 'user' ? 'YOU' : 'NEWTON';
            content += `[${timestamp}] ${role}:\n${item.text}\n\n`;
        });
        
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `newton-transcript-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.log('Transcript downloaded', 'success');
    }
    
    /**
     * Create audio message for WebSocket
     * @param {ArrayBuffer} audioData - PCM16 audio data
     * @returns {string} - JSON message
     */
    createAudioMessage(audioData) {
        // Convert ArrayBuffer to base64
        const bytes = new Uint8Array(audioData);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);
        
        return JSON.stringify({
            type: 'input_audio_buffer.append',
            audio: base64
        });
    }
    
    /**
     * End the call and clean up resources
     */
    async endCall() {
        this.log('Ending call...', 'info');
        this.updateStatus('Disconnecting...', false, false);
        
        await this.cleanup();
        
        this.startBtn.disabled = false;
        this.endBtn.disabled = true;
        this.isRecording = false;
        this.updateStatus('Call ended', false, false);
        
        this.log('Call ended successfully', 'success');
    }
    
    /**
     * Clean up all resources
     */
    async cleanup() {
        // Stop microphone
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        
        // Disconnect audio nodes
        if (this.audioWorkletNode) {
            this.audioWorkletNode.disconnect();
            this.audioWorkletNode = null;
        }
        
        // Close audio context
        if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
        }
        
        // Close WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Clear audio queue
        this.audioQueue = [];
        this.isPlaying = false;
        this.isConnected = false;
    }
    
    /**
     * Update status display
     * @param {string} message - Status message
     * @param {boolean} isError - Whether this is an error
     * @param {boolean} isConnected - Whether connected
     */
    updateStatus(message, isError = false, isConnected = false) {
        this.statusDiv.textContent = message;
        this.statusDiv.className = 'status';
        
        if (isError) {
            this.statusDiv.classList.add('error');
        } else if (isConnected) {
            this.statusDiv.classList.add('success');
            this.statusDiv.innerHTML = `
                <span class="indicator recording"></span>${message}
            `;
        }
    }
    
    /**
     * Log message to console and UI
     * @param {string} message - Log message
     * @param {string} type - Log type ('info', 'error', 'success')
     */
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logMessage = `[${timestamp}] ${message}`;
        
        console.log(logMessage);
        
        const logItem = document.createElement('div');
        logItem.className = `log-item ${type}`;
        logItem.textContent = logMessage;
        
        this.logDiv.appendChild(logItem);
        this.logDiv.scrollTop = this.logDiv.scrollHeight;
        
        // Keep only last 100 log items
        while (this.logDiv.children.length > 100) {
            this.logDiv.removeChild(this.logDiv.firstChild);
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} - Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize client when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.vernacClient = new VernacVoiceClient();
});
