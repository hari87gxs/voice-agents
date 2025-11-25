"""
Vernac - GXS Bank Voice-to-Voice Debt Collection Agent
FastAPI WebSocket Relay Server

This server acts as a pass-through bridge between the browser client and Azure OpenAI Realtime API.
It maintains bidirectional WebSocket connections and relays messages without transcoding audio.

Key Features:
- Stateless relay architecture for minimal latency
- Forwards Azure interruption events (speech_started) to enable barge-in
- Configures Azure OpenAI session with GXS Collector persona and VAD settings
- Serves static frontend files
"""

import os
import asyncio
import json
import logging
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import websockets
import uvicorn

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

# Validate configuration
if not all([AZURE_ENDPOINT, AZURE_API_KEY, AZURE_DEPLOYMENT]):
    raise ValueError("Missing Azure OpenAI configuration. Check .env file.")

# Load configuration from config.json
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

# Initialize FastAPI app
app = FastAPI(title="Vernac Voice Agent", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_system_instructions() -> str:
    """Build system instructions from config.json"""
    sp = CONFIG['system_prompt']
    tone = sp['tone_and_style']
    script = sp['conversation_script']
    
    # Handle different script structures
    if 'phase_1_greeting' in script:
        # Newton-style config
        greeting = script['phase_1_greeting']
        explanation = script['phase_2_explanation']
        followup = script['phase_3_followup']
        edges = script['edge_cases']
        
        instructions = f"""You are the **{sp['role']}**. Your goal is to {sp['goal']}.

**TONE & STYLE:**
- **{tone['description']}**
- **Interjections:** Use {', '.join(f'"{i}"' for i in tone['interjections'])} to acknowledge the user.
- **Phrasing:** {tone['phrasing_guide']}
- **Example:** {tone['example']}
- **NO CARICATURE:** {tone['caricature_warning']}

**CORE RULES:**
{chr(10).join(f'{i+1}. **{rule.split(":")[0]}:** {":".join(rule.split(":")[1:])}' for i, rule in enumerate(sp['core_rules']))}

**CONVERSATION SCRIPT (Follow this Flow):**

**{greeting['title']}**
"{greeting['opening']}"
*({greeting['wait_instruction']})*
- **If they give a name:** {greeting['if_name_given']}
- **If no name:** {greeting['if_no_name']}

**{explanation['title']}**
1. {explanation['step_1_acknowledge']}
2. {explanation['step_2_analogy']}
3. {explanation['step_3_fun_fact']}
4. {explanation['step_4_check']}

**Example:**
Q: {explanation['example_question']}
A: {explanation['example_answer']}

**{followup['title']}**
- **If they ask for more:** {followup['if_asks_more_detail']}
- **If confused:** {followup['if_confused']}
- **If changes topic:** {followup['if_changes_topic']}

**EDGE CASES:**
- **Too Advanced:** {edges['too_advanced']}
- **Not Science:** {edges['not_science']}
- **Wants to End:** {edges['wants_to_end']}

**LANGUAGE:** {sp['language_enforcement']}

**INTELLIGENCE:** {sp['intelligence_rules']}
"""
    else:
        # ABC Bank-style config (phase_1_verification, phase_2_waterfall, etc.)
        instructions = f"""You are the **{sp['role']}**. Your goal is to {sp['goal']}.

**TONE & STYLE:**
- **{tone['description']}**
- **Interjections:** Use {', '.join(f'"{i}"' for i in tone['interjections'])} to acknowledge the user.
- **Phrasing:** {tone['phrasing_guide']}
- **Example:** {tone['example']}
- **NO CARICATURE:** {tone['caricature_warning']}

**CORE RULES:**
{chr(10).join(f'{i+1}. **{rule.split(":")[0]}:** {":".join(rule.split(":")[1:])}' for i, rule in enumerate(sp['core_rules']))}

**CONVERSATION SCRIPT (Follow this Flow):**

**{script['phase_1_verification']['title']}**
"{script['phase_1_verification']['opening']}"
*({script['phase_1_verification']['wait_instruction']})*
"{script['phase_1_verification']['first_question']}"

**{script['phase_2_waterfall']['title']}**
- **If User says YES (3 days):**
  "{script['phase_2_waterfall']['if_yes_3_days']}"
- **If User says NO (to 3 days):**
  "{script['phase_2_waterfall']['if_no_3_days']}"
- **If User says NO (to 7 days):**
  "{script['phase_2_waterfall']['if_no_7_days']}"
- **{script['phase_2_waterfall'].get('if_customer_gives_specific_date', '')}**

**{script['phase_3_responses']['title']}**
- **User gives a Specific Date:**
  "{script['phase_3_responses']['user_gives_date']}"
- **User Refuses / No Date:**
  "{script['phase_3_responses']['user_refuses_no_date']}"

**{script['edge_cases']['title']}**
- **"I have financial difficulty" / "Bankrupt":**
  "{script['edge_cases']['financial_difficulty']}"
- **"Can I pay partial?":**
  "{script['edge_cases']['partial_payment']}"
- **"Is this a real person?":**
  "{script['edge_cases']['is_real_person']}"

**{sp['language_enforcement']}**

**{sp.get('intelligence_rules', '')}**
"""
    
    return instructions

def get_azure_realtime_url() -> str:
    """Construct Azure OpenAI Realtime WebSocket URL"""
    endpoint = AZURE_ENDPOINT.rstrip('/')
    # Remove https:// and replace with wss://
    ws_endpoint = endpoint.replace('https://', 'wss://')
    return f"{ws_endpoint}/openai/realtime?api-version=2024-10-01-preview&deployment={AZURE_DEPLOYMENT}"

def get_session_config() -> dict:
    """
    Create the session configuration for Azure OpenAI Realtime API.
    This sets up:
    - Audio formats (PCM16 24kHz)
    - System instructions (GXS Collector persona)
    - Voice selection
    - Server VAD settings for interruption detection
    """
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": build_system_instructions(),
            "voice": CONFIG['voice'],  # shimmer is more cheerful than alloy
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.6,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 600,
                "create_response": True
            },
            "temperature": 0.8,
            "max_response_output_tokens": 4096
        }
    }

async def relay_browser_to_azure(browser_ws: WebSocket, azure_ws: websockets.WebSocketClientProtocol):
    """
    Relay messages from browser to Azure OpenAI.
    Handles both text (JSON) and binary (audio) messages.
    """
    try:
        while True:
            # Receive message from browser
            message = await browser_ws.receive()
            
            if "text" in message:
                # JSON message (events, control messages)
                data = message["text"]
                logger.debug(f"Browser → Azure (text): {data[:100]}...")
                await azure_ws.send(data)
                
            elif "bytes" in message:
                # Binary message (audio data)
                data = message["bytes"]
                logger.debug(f"Browser → Azure (audio): {len(data)} bytes")
                await azure_ws.send(data)
                
    except WebSocketDisconnect:
        logger.info("Browser disconnected")
    except Exception as e:
        logger.error(f"Error in browser→azure relay: {e}")

async def relay_azure_to_browser(azure_ws: websockets.WebSocketClientProtocol, browser_ws: WebSocket):
    """
    Relay messages from Azure OpenAI to browser.
    CRITICAL: Forwards input_audio_buffer.speech_started events immediately for barge-in.
    """
    try:
        async for message in azure_ws:
            if isinstance(message, str):
                # JSON message (events, transcripts, etc.)
                logger.debug(f"Azure → Browser (text): {message[:100]}...")
                
                # Parse to check for interruption events
                try:
                    msg_data = json.loads(message)
                    event_type = msg_data.get("type", "")
                    
                    # CRITICAL: Forward speech_started immediately for barge-in
                    if event_type == "input_audio_buffer.speech_started":
                        logger.info("🎤 User started speaking - triggering barge-in")
                    
                    # Log important events
                    if event_type in ["conversation.item.created", "response.done", "error"]:
                        logger.info(f"Event: {event_type}")
                        
                except json.JSONDecodeError:
                    pass
                
                await browser_ws.send_text(message)
                
            elif isinstance(message, bytes):
                # Binary message (audio data)
                logger.debug(f"Azure → Browser (audio): {len(message)} bytes")
                await browser_ws.send_bytes(message)
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Azure connection closed")
    except Exception as e:
        logger.error(f"Error in azure→browser relay: {e}")

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint that handles the relay between browser and Azure OpenAI.
    
    Flow:
    1. Accept browser connection
    2. Connect to Azure OpenAI
    3. Send session configuration
    4. Start bidirectional relay
    """
    await websocket.accept()
    logger.info("✓ Browser WebSocket connected")
    
    azure_ws = None
    
    try:
        # Connect to Azure OpenAI Realtime API
        azure_url = get_azure_realtime_url()
        headers = {
            "api-key": AZURE_API_KEY,
        }
        
        logger.info("Connecting to Azure OpenAI...")
        azure_ws = await websockets.connect(
            azure_url,
            extra_headers=headers,
            ping_interval=20,
            ping_timeout=10
        )
        logger.info("✓ Azure OpenAI WebSocket connected")
        
        # Send session configuration immediately
        session_config = get_session_config()
        await azure_ws.send(json.dumps(session_config))
        logger.info("✓ Session configuration sent")
        
        # Send initial greeting as a conversation item to trigger immediate response
        initial_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": CONFIG['intro_message']
                    }
                ]
            }
        }
        await azure_ws.send(json.dumps(initial_item))
        
        # Trigger response generation
        create_response = {
            "type": "response.create"
        }
        await azure_ws.send(json.dumps(create_response))
        logger.info("✓ Initial greeting triggered")
        
        # Start bidirectional relay
        browser_to_azure_task = asyncio.create_task(
            relay_browser_to_azure(websocket, azure_ws)
        )
        azure_to_browser_task = asyncio.create_task(
            relay_azure_to_browser(azure_ws, websocket)
        )
        
        # Wait for either task to complete (usually means disconnect)
        done, pending = await asyncio.wait(
            [browser_to_azure_task, azure_to_browser_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": {"message": str(e)}
        }))
        
    finally:
        # Clean up connections
        if azure_ws:
            await azure_ws.close()
        try:
            await websocket.close()
        except:
            pass
        logger.info("✗ WebSocket connections closed")

@app.get("/")
async def get_index():
    """Serve the main HTML page"""
    return FileResponse("index.html")

@app.get("/client.js")
async def get_client_js():
    """Serve the client JavaScript"""
    return FileResponse("client.js", media_type="application/javascript")

@app.get("/audio-processor.js")
async def get_audio_processor():
    """Serve the AudioWorklet processor"""
    return FileResponse("audio-processor.js", media_type="application/javascript")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Vernac Voice Agent",
        "azure_configured": bool(AZURE_ENDPOINT and AZURE_API_KEY and AZURE_DEPLOYMENT)
    }

if __name__ == "__main__":
    logger.info(f"🚀 Starting Vernac Voice Agent Server on {HOST}:{PORT}")
    logger.info(f"📡 Azure Endpoint: {AZURE_ENDPOINT}")
    logger.info(f"🎯 Deployment: {AZURE_DEPLOYMENT}")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
