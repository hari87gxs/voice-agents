"""
CXBuddy - GXS Bank Customer Experience AI Agent
FastAPI WebSocket Relay Server with Tool Calling Support

Enhanced features:
- Tool calling for knowledge base search
- Mock knowledge search function (will be replaced with Azure OpenAI vector store)
- Handles function_call events from Realtime API
"""

import os
import asyncio
import json
import logging
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import websockets
import uvicorn

# Import vector store manager
import vector_store as vs_module

# Import ticketing system
import ticketing

# Import GXS API client
import gxs_api

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
PORT = int(os.getenv("PORT", 8003))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8003,http://127.0.0.1:8003").split(",")

# Validate configuration
if not all([AZURE_ENDPOINT, AZURE_API_KEY, AZURE_DEPLOYMENT]):
    raise ValueError("Missing Azure OpenAI configuration. Check .env file.")

# Load configuration for both agents
CONFIG_RILEY_FILE = os.path.join(os.path.dirname(__file__), 'config_riley.json')
CONFIG_HARI_FILE = os.path.join(os.path.dirname(__file__), 'config_hari.json')

with open(CONFIG_RILEY_FILE, 'r', encoding='utf-8') as f:
    CONFIG_RILEY = json.load(f)

with open(CONFIG_HARI_FILE, 'r', encoding='utf-8') as f:
    CONFIG_HARI = json.load(f)

# Default to Riley for backward compatibility
CONFIG = CONFIG_RILEY

# Knowledge base configuration
KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'gxs_help_content', 'gxs_help_consolidated.txt')
USE_VECTOR_STORE = os.getenv('USE_VECTOR_STORE', 'true').lower() == 'true'
EMBEDDING_DEPLOYMENT = os.getenv('AZURE_EMBEDDING_DEPLOYMENT', 'text-embedding-ada-002')

# Initialize FastAPI app
app = FastAPI(title="CXBuddy - GXS Voice Agent", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    Initialize services in background after server starts.
    This allows Cloud Run health checks to pass immediately.
    """
    async def init_services():
        # Initialize ticketing system
        try:
            logger.info("🔄 Initializing ticketing system...")
            ticketing.initialize_ticketing("./tickets.db")
            logger.info("✅ Ticketing system ready")
        except Exception as e:
            logger.error(f"❌ Ticketing initialization failed: {e}")
        
        # Initialize vector store if enabled
        if USE_VECTOR_STORE:
            try:
                logger.info("🔄 Initializing vector store (background)...")
                vs_module.initialize_vector_store(
                    knowledge_file=KNOWLEDGE_BASE_PATH,
                    force_reindex=False,
                    azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
                    azure_api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
                    embedding_deployment=EMBEDDING_DEPLOYMENT
                )
                logger.info("✅ Vector store ready")
            except Exception as e:
                logger.error(f"❌ Vector store initialization failed: {e}")
                logger.info("⚠️  Falling back to keyword search")
    
    # Run initialization in background
    asyncio.create_task(init_services())
    logger.info("🚀 Server started - initializing services in background...")



def search_knowledge_base(query: str) -> str:
    """
    Search knowledge base using vector store (semantic search) or fallback to keyword search.
    """
    if USE_VECTOR_STORE and vs_module.vector_store is not None:
        # Use semantic search with ChromaDB
        logger.info(f"🔍 Semantic search: {query}")
        return vs_module.vector_store.search(query, n_results=3)
    else:
        # Fallback to keyword search (legacy)
        logger.info(f"🔍 Keyword search (fallback): {query}")
        return keyword_search_fallback(query)


def keyword_search_fallback(query: str) -> str:
    """
    Fallback keyword search when vector store is not available.
    """
    import re
    
    # Load knowledge base if not already loaded
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            knowledge_base = f.read()
    except FileNotFoundError:
        return "Knowledge base not available. Please run scraper.py first."
    
    # Normalize query - split into keywords, remove punctuation
    query_lower = query.lower()
    words = re.findall(r'\b[a-z]+\b', query_lower)
    stop_words = {'are', 'the', 'is', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'from', 'my', 'your', 'i', 'you', 'it', 'this', 'that', 'be', 'can', 'do', 'does', 'what', 'how', 'when', 'where', 'why', 'which'}
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    sections = knowledge_base.split('\n\n')
    matches = []
    
    for section in sections:
        section_lower = section.lower()
        section_len = len(section.strip())
        
        if section_len < 100:
            continue
        
        keyword_matches = sum(1 for kw in keywords if kw in section_lower)
        
        if keyword_matches > 0:
            score = keyword_matches * 100
            if keyword_matches == len(keywords):
                score += 200
            score = score / (section_len / 100)
            
            lines = [l.strip() for l in section.strip().split('\n') if l.strip()]
            content_lines = [l for l in lines if not l.startswith('=') and not l.startswith('SOURCE:') and not l.startswith('TITLE:')]
            
            if content_lines:
                snippet = ' '.join(content_lines[:10])[:600]
                matches.append((score, snippet))
    
    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)
        unique_matches = []
        for _, snippet in matches[:10]:
            if snippet not in unique_matches:
                unique_matches.append(snippet)
            if len(unique_matches) >= 3:
                break
        
        result = '\n\n---\n\n'.join(unique_matches)
        logger.info(f"✓ Found {len(matches)} matches (returning top {len(unique_matches)})")
        return result
    else:
        logger.warning(f"⚠ No matches found for query: {query}")
        return "No information found for this query. Please check help.gxs.com.sg directly."


def build_system_instructions() -> str:
    """Build system instructions from config.json"""
    sp = CONFIG['system_prompt']
    
    instructions = f"""You are **{sp['role']}**. {sp['goal']}

**TONE & STYLE:**
{sp['tone_and_style']['description']}
- Use interjections: {', '.join(sp['tone_and_style']['interjections'])}
- Phrasing: {sp['tone_and_style']['phrasing_guide']}

**CORE RULES:**
{chr(10).join(f'- {rule}' for rule in sp['core_rules'])}

**CONVERSATION FLOW:**
"""
    
    # Dynamically build conversation script
    script = sp['conversation_script']
    for phase_key, phase_content in script.items():
        if isinstance(phase_content, dict) and 'title' in phase_content:
            instructions += f"\n**{phase_content['title']}**\n"
            for field_key, field_value in phase_content.items():
                if field_key != 'title':
                    instructions += f"- {field_key}: {field_value}\n"
    
    instructions += f"\n**LANGUAGE:** {sp['language_enforcement']}"
    
    return instructions


def get_azure_realtime_url() -> str:
    """Construct Azure OpenAI Realtime WebSocket URL"""
    endpoint = AZURE_ENDPOINT.rstrip('/')
    ws_endpoint = endpoint.replace('https://', 'wss://')
    return f"{ws_endpoint}/openai/realtime?api-version=2024-10-01-preview&deployment={AZURE_DEPLOYMENT}"


def get_session_config(agent_config=None) -> dict:
    """
    Create the session configuration for Azure OpenAI Realtime API.
    Includes tools definition for function calling.
    """
    if agent_config is None:
        agent_config = CONFIG
        
    config = {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": agent_config.get('instructions', ''),
            "voice": agent_config.get('voice', 'shimmer'),
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": agent_config.get('turn_detection', {
                "type": "server_vad",
                "threshold": 0.6,
                "prefix_padding_ms": 200,
                "silence_duration_ms": 400,
                "create_response": True
            }),
            "temperature": 0.8,
            "max_response_output_tokens": 4096
        }
    }
    
    # Add tools if defined in config
    if 'tools' in agent_config:
        config['session']['tools'] = agent_config['tools']
        logger.info(f"✓ Registered {len(agent_config['tools'])} tools")
    
    return config


async def handle_function_call(call_id: str, function_name: str, arguments: str, azure_ws: websockets.WebSocketClientProtocol, browser_ws: WebSocket = None):
    """
    Handle function call from Azure OpenAI Realtime API.
    Executes the function and sends result back.
    Sends handoff signal to browser if agent switch requested.
    """
    logger.info(f"🔧 Function called: {function_name} with args: {arguments}")
    
    try:
        args = json.loads(arguments)
        result = None
        handoff_target = None
        
        # Knowledge base search
        if function_name == "search_gxs_help_center":
            query = args.get("query", "")
            result = search_knowledge_base(query)
        
        # Account balance
        elif function_name == "get_account_balance":
            result = await gxs_api.gxs_api.get_account_balance()
        
        # Account details
        elif function_name == "get_account_details":
            result = await gxs_api.gxs_api.get_account_details()
        
        # Recent transactions
        elif function_name == "get_recent_transactions":
            limit = args.get("limit", 5)
            result = await gxs_api.gxs_api.get_recent_transactions(limit)
        
        # Card details
        elif function_name == "get_card_details":
            result = await gxs_api.gxs_api.get_card_details()
        
        # Freeze card
        elif function_name == "freeze_card":
            result = await gxs_api.gxs_api.freeze_card()
        
        # Unfreeze card
        elif function_name == "unfreeze_card":
            result = await gxs_api.gxs_api.unfreeze_card()
        
        # Handoff to Hari (from Riley)
        elif function_name == "handoff_to_hari":
            reason = args.get("reason", "account inquiry")
            logger.info(f"🔄 Handoff: RILEY → HARI (reason: {reason})")
            result = "Connecting you to Hari now..."
            handoff_target = "hari"
        
        # Handoff to Riley (from Hari)
        elif function_name == "handoff_to_riley":
            reason = args.get("reason", "general inquiry")
            logger.info(f"🔄 Handoff: HARI → RILEY (reason: {reason})")
            result = "Let me connect you to Riley..."
            handoff_target = "riley"
        
        # Check product ownership (for Hari)
        elif function_name == "check_product_ownership":
            product_type = args.get("product_type", "")
            # Mock: users only have account + card, no loans/investments/insurance
            has_product = product_type in []
            result = json.dumps({
                "has_product": has_product,
                "product_type": product_type,
                "should_handoff": not has_product
            })
        
        else:
            result = f"Unknown function: {function_name}"
        
        # Convert dict results to JSON string
        if isinstance(result, dict):
            result = json.dumps(result)
        
        # Send function result back to Azure
        response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result
            }
        }
        
        await azure_ws.send(json.dumps(response))
        
        # Trigger response generation
        await azure_ws.send(json.dumps({"type": "response.create"}))
        
        logger.info(f"✓ Function result sent for call_id: {call_id}")
        
        # If handoff requested, wait briefly for AI to finish speaking then signal browser
        if handoff_target and browser_ws:
            # Wait for AI to finish speaking the handoff message (3 seconds for complete sentence)
            await asyncio.sleep(3.0)
            logger.info(f"📤 Sending handoff signal to browser: {handoff_target}")
            
            try:
                await browser_ws.send_text(json.dumps({
                    "type": "agent.handoff",
                    "target_agent": handoff_target,
                    "message": f"Transferring to {handoff_target.title()}..."
                }))
            except Exception as e:
                logger.error(f"Failed to send handoff signal: {e}")
        
        return handoff_target
        
    except Exception as e:
        logger.error(f"✗ Error handling function call: {e}")
        
        # Send error back
        error_response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": f"Error: {str(e)}"
            }
        }
        await azure_ws.send(json.dumps(error_response))
        return None
        return None


async def relay_browser_to_azure(browser_ws: WebSocket, azure_ws: websockets.WebSocketClientProtocol):
    """Relay messages from browser to Azure OpenAI"""
    try:
        while True:
            message = await browser_ws.receive()
            
            if "text" in message:
                data = message["text"]
                logger.debug(f"Browser → Azure (text): {data[:100]}...")
                await azure_ws.send(data)
                
            elif "bytes" in message:
                data = message["bytes"]
                logger.debug(f"Browser → Azure (audio): {len(data)} bytes")
                await azure_ws.send(data)
                
    except WebSocketDisconnect:
        logger.info("Browser disconnected")
    except Exception as e:
        logger.error(f"Error in browser→azure relay: {e}")


async def relay_browser_to_azure_with_logging(browser_ws: WebSocket, azure_ws: websockets.WebSocketClientProtocol, ticket_id: Optional[str]):
    """Relay messages from browser to Azure OpenAI with ticket logging"""
    try:
        while True:
            try:
                message = await browser_ws.receive()
            except RuntimeError as e:
                # WebSocket disconnected (happens during handoff)
                if "disconnect" in str(e).lower():
                    logger.info("Browser WebSocket disconnected (likely handoff)")
                    return
                raise
            
            if "text" in message:
                data = message["text"]
                logger.debug(f"Browser → Azure (text): {data[:100]}...")
                
                # Try to extract user transcription for logging
                if ticket_id:
                    try:
                        msg_data = json.loads(data)
                        # Look for input_audio_buffer.commit or conversation.item.create with text
                        if msg_data.get("type") == "conversation.item.create":
                            item = msg_data.get("item", {})
                            if item.get("type") == "message" and item.get("role") == "user":
                                content = item.get("content", [])
                                for c in content:
                                    if c.get("type") == "input_text":
                                        user_text = c.get("text", "")
                                        ticketing.ticketing_system.log_interaction(
                                            ticket_id=ticket_id,
                                            speaker="user",
                                            message=user_text,
                                            tool_calls=None
                                        )
                    except Exception as e:
                        logger.debug(f"Could not log user message: {e}")
                
                await azure_ws.send(data)
                
            elif "bytes" in message:
                data = message["bytes"]
                logger.debug(f"Browser → Azure (audio): {len(data)} bytes")
                await azure_ws.send(data)
                
    except WebSocketDisconnect:
        logger.info("Browser disconnected gracefully")
    except Exception as e:
        if "disconnect" not in str(e).lower():
            logger.error(f"Error in browser→azure relay: {e}")


async def relay_azure_to_browser(azure_ws: websockets.WebSocketClientProtocol, browser_ws: WebSocket):
    """
    Relay messages from Azure OpenAI to browser.
    Intercepts function_call events to execute tools.
    """
    try:
        async for message in azure_ws:
            if isinstance(message, str):
                logger.debug(f"Azure → Browser (text): {message[:100]}...")
                
                try:
                    msg_data = json.loads(message)
                    event_type = msg_data.get("type", "")
                    
                    # Handle function calls
                    if event_type == "response.function_call_arguments.done":
                        call_id = msg_data.get("call_id")
                        function_name = msg_data.get("name")
                        arguments = msg_data.get("arguments", "{}")
                        
                        # Execute function in background
                        asyncio.create_task(
                            handle_function_call(call_id, function_name, arguments, azure_ws)
                        )
                    
                    # Log important events
                    if event_type == "input_audio_buffer.speech_started":
                        logger.info("🎤 User started speaking")
                    elif event_type == "error":
                        error_details = msg_data.get("error", {})
                        logger.error(f"❌ Azure API Error: {json.dumps(error_details)}")
                        logger.info(f"Event: {event_type}")
                    elif event_type in ["conversation.item.created", "response.done"]:
                        logger.info(f"Event: {event_type}")
                        
                except json.JSONDecodeError:
                    pass
                
                await browser_ws.send_text(message)
                
            elif isinstance(message, bytes):
                logger.debug(f"Azure → Browser (audio): {len(message)} bytes")
                await browser_ws.send_bytes(message)
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Azure connection closed")
    except Exception as e:
        logger.error(f"Error in azure→browser relay: {e}")


async def relay_azure_to_browser_with_logging(azure_ws: websockets.WebSocketClientProtocol, browser_ws: WebSocket, ticket_id: Optional[str]):
    """
    Relay messages from Azure OpenAI to browser with ticket logging.
    Intercepts function_call events to execute tools and logs agent responses.
    """
    try:
        async for message in azure_ws:
            if isinstance(message, str):
                logger.debug(f"Azure → Browser (text): {message[:100]}...")
                
                try:
                    msg_data = json.loads(message)
                    event_type = msg_data.get("type", "")
                    
                    # Handle function calls
                    if event_type == "response.function_call_arguments.done":
                        call_id = msg_data.get("call_id")
                        function_name = msg_data.get("name")
                        arguments = msg_data.get("arguments", "{}")
                        
                        # Log tool call to ticket
                        if ticket_id:
                            try:
                                ticketing.ticketing_system.log_interaction(
                                    ticket_id=ticket_id,
                                    speaker="agent",
                                    message=f"[Tool Call: {function_name}]",
                                    tool_calls=[{"name": function_name, "arguments": arguments}]
                                )
                            except Exception as e:
                                logger.error(f"Failed to log tool call: {e}")
                        
                        # Execute function (with browser_ws for handoff signaling)
                        asyncio.create_task(
                            handle_function_call(call_id, function_name, arguments, azure_ws, browser_ws)
                        )
                    
                    # Log agent transcriptions
                    elif event_type == "response.audio_transcript.done":
                        transcript = msg_data.get("transcript", "")
                        if ticket_id and transcript:
                            try:
                                ticketing.ticketing_system.log_interaction(
                                    ticket_id=ticket_id,
                                    speaker="agent",
                                    message=transcript,
                                    tool_calls=None
                                )
                            except Exception as e:
                                logger.error(f"Failed to log agent transcript: {e}")
                        
                        # Store in conversation history for handoff context
                        if hasattr(browser_ws, 'state') and transcript:
                            if not hasattr(browser_ws.state, 'conversation_history'):
                                browser_ws.state.conversation_history = []
                            browser_ws.state.conversation_history.append({
                                "role": "assistant",
                                "text": transcript
                            })
                    
                    # Log user transcriptions
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = msg_data.get("transcript", "")
                        if ticket_id and transcript:
                            try:
                                ticketing.ticketing_system.log_interaction(
                                    ticket_id=ticket_id,
                                    speaker="user",
                                    message=transcript,
                                    tool_calls=None
                                )
                            except Exception as e:
                                logger.error(f"Failed to log user transcript: {e}")
                        
                        # Store in conversation history for handoff context
                        if hasattr(browser_ws, 'state') and transcript:
                            if not hasattr(browser_ws.state, 'conversation_history'):
                                browser_ws.state.conversation_history = []
                            browser_ws.state.conversation_history.append({
                                "role": "user",
                                "text": transcript
                            })
                    
                    # Log important events
                    if event_type == "input_audio_buffer.speech_started":
                        logger.info("🎤 User started speaking")
                    elif event_type == "error":
                        error_details = msg_data.get("error", {})
                        logger.error(f"❌ Azure API Error: {json.dumps(error_details)}")
                        logger.info(f"Event: {event_type}")
                    elif event_type in ["conversation.item.created", "response.done"]:
                        logger.info(f"Event: {event_type}")
                        
                except json.JSONDecodeError:
                    pass
                
                await browser_ws.send_text(message)
                
            elif isinstance(message, bytes):
                logger.debug(f"Azure → Browser (audio): {len(message)} bytes")
                await browser_ws.send_bytes(message)
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Azure connection closed")
    except Exception as e:
        logger.error(f"Error in azure→browser relay: {e}")


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint with ticketing integration and dual-agent support"""
    await websocket.accept()
    logger.info("✓ Browser WebSocket connected")
    
    # Generate session ID for this connection
    import uuid
    session_id = str(uuid.uuid4())
    
    # Conversation history for handoff context
    conversation_history = []
    
    # Check for JWT token in query params
    jwt_token = websocket.query_params.get('jwt', None)
    is_authenticated = False
    
    if jwt_token:
        gxs_api.gxs_api.set_jwt(jwt_token)
        customer_name = gxs_api.gxs_api.get_user_name()
        is_authenticated = True
        logger.info(f"🔐 Authenticated user: {customer_name}")
    else:
        customer_name = "Guest"
        gxs_api.gxs_api.clear_jwt()
        logger.info("⚠️ No JWT token provided - Riley (general support) mode")
    
    # Determine starting agent: Hari if authenticated, Riley if not
    current_agent = "hari" if is_authenticated else "riley"
    current_config = CONFIG_HARI if is_authenticated else CONFIG_RILEY
    logger.info(f"🤖 Starting with agent: {current_agent.upper()}")
    
    # Create ticket for this call
    ticket_id = None
    try:
        ticket_id = ticketing.ticketing_system.create_ticket(
            session_id=session_id,
            customer_name=customer_name,
            category=None,  # Will be auto-categorized
            priority="normal"
        )
        logger.info(f"🎫 Ticket created: {ticket_id}")
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
    
    azure_ws = None
    
    try:
        # Connect to Azure OpenAI
        azure_url = get_azure_realtime_url()
        extra_headers = {
            "api-key": AZURE_API_KEY
        }
        
        logger.info(f"Connecting to Azure OpenAI: {azure_url[:50]}...")
        azure_ws = await websockets.connect(azure_url, extra_headers=extra_headers)
        logger.info("✓ Azure WebSocket connected")
        
        # Send session configuration with agent-specific config
        session_config = get_session_config(current_config)
        await azure_ws.send(json.dumps(session_config))
        logger.info(f"✓ Session configured for {current_agent.upper()}")
        
        # Trigger greeting
        await azure_ws.send(json.dumps({"type": "response.create"}))
        logger.info(f"✓ {current_agent.upper()} greeting triggered")
        
        # Log greeting to ticket
        if ticket_id:
            try:
                ticketing.ticketing_system.log_interaction(
                    ticket_id=ticket_id,
                    speaker="agent",
                    message=f"[{current_agent.title()} greeting started]",
                    tool_calls=None
                )
            except Exception as e:
                logger.error(f"Failed to log greeting: {e}")
        
        # Start bidirectional relay with ticket logging
        # Use return_exceptions=True so handoff disconnects don't kill the whole connection
        results = await asyncio.gather(
            relay_browser_to_azure_with_logging(websocket, azure_ws, ticket_id),
            relay_azure_to_browser_with_logging(azure_ws, websocket, ticket_id),
            return_exceptions=True
        )
        
        # Log any unexpected exceptions (not disconnect-related)
        for result in results:
            if isinstance(result, Exception) and "disconnect" not in str(result).lower():
                logger.error(f"Relay task error: {result}")
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
    finally:
        # Close ticket when call ends
        if ticket_id:
            try:
                ticketing.ticketing_system.close_session(ticket_id, auto_categorize=True)
                logger.info(f"🎫 Ticket closed: {ticket_id}")
            except Exception as e:
                logger.error(f"Failed to close ticket: {e}")
        
        if azure_ws:
            await azure_ws.close()
        logger.info("✗ Connection closed")


@app.get("/")
async def serve_landing():
    """Serve the landing page"""
    return FileResponse("landing.html")

@app.get("/index.html")
async def serve_frontend():
    """Serve the main voice agent page"""
    return FileResponse("index.html")


@app.get("/tickets")
async def serve_tickets_dashboard():
    """Serve the ticketing dashboard"""
    return FileResponse("tickets.html")


@app.get("/client.js")
async def serve_client_js():
    """Serve client JavaScript"""
    return FileResponse("client.js", media_type="application/javascript")


@app.get("/audio-processor.js")
async def serve_audio_processor():
    """Serve audio processor"""
    return FileResponse("audio-processor.js", media_type="application/javascript")


@app.get("/mock_gxs_app.html")
async def serve_mock_app():
    """Serve mock GXS app for Hari"""
    return FileResponse("mock_gxs_app.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "CXBuddy", "version": "1.0.0"}


@app.get("/api/tickets/stats")
async def get_ticket_stats():
    """Get ticketing system statistics"""
    try:
        stats = ticketing.ticketing_system.get_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Failed to get ticket stats: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/tickets")
async def list_tickets(status: Optional[str] = None, limit: int = 50, offset: int = 0):
    """List tickets with optional filtering"""
    try:
        tickets = ticketing.ticketing_system.get_tickets(
            status=status,
            limit=limit,
            offset=offset
        )
        return {
            "status": "success",
            "data": tickets,
            "count": len(tickets)
        }
    except Exception as e:
        logger.error(f"Failed to list tickets: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/tickets/{ticket_id}")
async def get_ticket_detail(ticket_id: str):
    """Get full ticket details including transcript"""
    try:
        ticket = ticketing.ticketing_system.get_ticket(ticket_id)
        if ticket:
            return {
                "status": "success",
                "data": ticket
            }
        else:
            return {
                "status": "error",
                "message": "Ticket not found"
            }
    except Exception as e:
        logger.error(f"Failed to get ticket: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    logger.info(f"🚀 Starting CXBuddy on {HOST}:{PORT}")
    logger.info(f"🔧 Tools registered: {len(CONFIG.get('tools', []))}")
    logger.info("⚡ Services will initialize in background after startup")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
