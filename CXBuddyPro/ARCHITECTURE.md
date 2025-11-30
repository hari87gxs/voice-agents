# CXBuddy Architecture

## System Overview

CXBuddy is a voice-enabled AI customer service agent for GXS Bank, built using Azure OpenAI's GPT-4 Realtime API with advanced RAG (Retrieval Augmented Generation) capabilities. The system provides real-time conversational support with dynamic knowledge retrieval from the GXS Help Center.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Browser (index.html)                       │   │
│  │  • GXS Purple Branding                                       │   │
│  │  • Microphone Input via AudioWorklet                         │   │
│  │  • Real-time Transcript Display                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (24kHz PCM16 Audio)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI SERVER                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    server.py (Port 8003)                      │   │
│  │  • WebSocket Relay to Azure OpenAI                           │   │
│  │  • Tool Call Handler (search_gxs_help_center)                │   │
│  │  • Session Management                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                                              │
          │ WebSocket                                    │ Function Call
          │ (realtime.openai.azure.com)                  │
          ▼                                              ▼
┌──────────────────────────┐              ┌──────────────────────────┐
│   AZURE OPENAI GPT-4o    │              │   KNOWLEDGE RETRIEVAL    │
│   Realtime API           │              │                          │
│  • Voice: Shimmer        │◄─────────────│  vector_store.py         │
│  • Tool Calling          │  Results     │  • ChromaDB              │
│  • Conversation Flow     │              │  • Semantic Search       │
└──────────────────────────┘              └──────────────────────────┘
                                                        │
                                                        │ Embedding
                                                        ▼
                                          ┌──────────────────────────┐
                                          │  AZURE OPENAI EMBEDDING  │
                                          │  text-embedding-3-large  │
                                          │  • 3072 dimensions       │
                                          │      │
                                          └──────────────────────────┘
                                                        │
                                                        │ Read
                                                        ▼
                                          ┌──────────────────────────┐
                                          │   KNOWLEDGE BASE         │
                                          │  gxs_help_content/       │
                                          │  • 200 pages (target)    │
                                          │  • FAQ answers           │
                                          │  • Product docs          │
                                          └──────────────────────────┘
                                                        ▲
                                                        │ Scrape
                                                        │
                                          ┌──────────────────────────┐
                                          │    WEB SCRAPER           │
                                          │    scraper.py            │
                                          │  • BeautifulSoup4        │
                                          │  • BFS Crawling          │
                                          │  • Respectful (2s delay) │
                                          └──────────────────────────┘
                                                        ▲
                                                        │ Source
                                                        │
                                          ┌──────────────────────────┐
                                          │   help.gxs.com.sg        │
                                          │   GXS Help Center        │
                                          └──────────────────────────┘
```

## Component Details

### 1. Frontend (Browser)

**Files:** `index.html`, `client.js`, `audio-processor.js`

**Responsibilities:**
- Capture microphone audio at 24kHz mono PCM16
- Establish WebSocket connection to FastAPI server
- Stream audio chunks to server
- Receive and play back audio responses
- Display real-time transcript with role labels (Riley/User)
- GXS purple gradient branding (#6b46c1, #805ad5)

**Audio Processing Pipeline:**
```
Microphone → AudioWorklet → PCM16 Conversion → WebSocket → Server
Server → Base64 Audio → ArrayBuffer → AudioContext → Speakers
```

**Key Features:**
- Non-blocking audio processing
- Real-time VAD (Voice Activity Detection) handled by Azure
- Automatic session management
- Error handling and reconnection logic

### 2. Backend Server (FastAPI)

**File:** `server.py`

**Responsibilities:**
- WebSocket relay between browser and Azure OpenAI Realtime API
- Tool call interception and execution
- Dynamic system prompt building from config.json
- Session lifecycle management
- Error handling and logging

**WebSocket Flow:**
```
1. Client connects → Establish Azure WebSocket
2. Send session.update with config (voice, tools, instructions)
3. Relay audio: Client ↔ Server ↔ Azure
4. Intercept function_call events → Execute search → Return results
5. Azure generates response → Stream to client
```

**Tool Calling Mechanism:**
```python
# Azure sends: response.function_call_arguments.done
{
    "call_id": "call_xyz123",
    "name": "search_gxs_help_center",
    "arguments": "{\"query\": \"how to freeze flexicard\"}"
}

# Server executes search → Returns:
{
    "type": "conversation.item.create",
    "item": {
        "type": "function_call_output",
        "call_id": "call_xyz123",
        "output": "Freeze instructions..."
    }
}

# Trigger response generation:
{
    "type": "response.create"
}
```

### 3. Knowledge Retrieval System

**Files:** `vector_store.py`, `scraper.py`

#### 3.1 Web Scraper (`scraper.py`)

**Purpose:** Crawl help.gxs.com.sg and extract help content

**Algorithm:**
- BFS (Breadth-First Search) crawling
- Same-domain link following
- Content extraction with BeautifulSoup
- Metadata tracking (source URL, title, word count)

**Configuration:**
- `max_pages`: 200 (configurable)
- `delay`: 2.0 seconds (respectful crawling)
- `min_words`: 20 (filter thin content)

**Output:**
```
gxs_help_content/
├── page_001_GXS FlexiCard.txt
├── page_002_GXS Savings Account.txt
├── ...
├── gxs_help_consolidated.txt  # All content combined
└── metadata.json              # Scraping stats
```

#### 3.2 Vector Store (`vector_store.py`)

**Purpose:** Semantic search over GXS help content using ChromaDB

**Components:**

**Embedding Model:**
- Azure OpenAI text-embedding-3-large
- 3072 dimensions (high quality)
- Endpoint: genai-varsha-dev.cognitiveservices.azure.com
- API Version: 2023-05-15

**Vector Database:**
- ChromaDB (persistent client)
- Collection: `gxs_help_center`
- Storage: `./chroma_db/`

**Chunking Strategy:**
```python
# Split text into 500-char chunks with 100-char overlap
chunk_size = 500
overlap = 100

# Smart boundary detection:
# - Prefer sentence breaks (. ? !)
# - Fall back to paragraph breaks (\n\n)
# - Preserve context across chunks
```

**Search Algorithm:**
```python
1. Convert query to embedding (3072-dim vector)
2. ChromaDB cosine similarity search
3. Return top 3 most relevant chunks
4. Deduplicate by content
5. Format with metadata (source, title)
```

**Performance:**
- Embedding latency: ~100-200ms
- Search latency: <50ms (ChromaDB)
- Total retrieval: ~150-250ms

### 4. Configuration System

**File:** `config.json`

**Structure:**
```json
{
    "voice": "shimmer",
    "intro_message": "Hi there! I'm Riley...",
    "agent_name": "Riley",
    "system_prompt": {
        "identity": "GXS Customer Experience Specialist",
        "core_rules": ["ALWAYS USE THE TOOL", "SYNTHESIZE DON'T READ", ...],
        "conversation_flow": {
            "phase_1_greeting": "Ask name, personalize",
            "phase_2_answering": "Use tool, provide steps",
            "edge_cases": "Handle unknown queries"
        }
    },
    "tools": [{
        "type": "function",
        "name": "search_gxs_help_center",
        "description": "REQUIRED: Use this tool to look up information...",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "User's question or search query"
                }
            },
            "required": ["query"]
        }
    }]
}
```

**Key Configurations:**
- **voice**: "shimmer" (friendly, approachable female voice)
- **tools**: Defines search_gxs_help_center function
- **system_prompt**: Riley's persona, rules, conversation flow
- **intro_message**: First thing Riley says

## Data Flow

### User Query Flow

```
1. User speaks: "How do I freeze my FlexiCard?"
   ↓
2. Browser captures audio → Sends to server
   ↓
3. Server relays to Azure OpenAI Realtime API
   ↓
4. Azure transcribes speech → Detects function call needed
   ↓
5. Azure sends: response.function_call_arguments.done
   {
     "name": "search_gxs_help_center",
     "arguments": "{\"query\": \"how to freeze flexicard\"}"
   }
   ↓
6. Server intercepts → Calls vector_store.search()
   ↓
7. Vector store:
   a. Embeds query → [0.031, -0.002, 0.011, ...] (3072 dims)
   b. ChromaDB similarity search
   c. Returns top 3 chunks with freeze instructions
   ↓
8. Server sends results back to Azure:
   {
     "type": "conversation.item.create",
     "item": {
       "type": "function_call_output",
       "output": "You can freeze your GXS FlexiCard by:
                  1. Log in to the GXS Bank app
                  2. On the GXS FlexiCard homescreen, tap 'Freeze'
                  3. Confirm the Freeze request"
     }
   }
   ↓
9. Server triggers response: {"type": "response.create"}
   ↓
10. Azure generates natural language response using function results
   ↓
11. Azure streams audio response back
   ↓
12. Server relays to browser → User hears Riley's answer
```

### Scraper Update Flow

```
1. Run: python3 scraper.py
   ↓
2. BFS crawl help.gxs.com.sg
   - Visit up to 200 pages
   - 2 second delay between requests
   - Extract text content (min 20 words)
   ↓
3. Save to gxs_help_content/
   - Individual page files
   - Consolidated file
   - Metadata JSON
   ↓
4. Vector store indexes on next server start
   OR
   Manually trigger: python3 -c "from vector_store import initialize_vector_store; initialize_vector_store(..., force_reindex=True)"
   ↓
5. ChromaDB builds vector index
   - Chunk text (500 chars, 100 overlap)
   - Embed chunks (batch size 50)
   - Store in chroma_db/
   ↓
6. New knowledge available for searches
```

## Technology Stack

### Backend
- **FastAPI**: Web framework, WebSocket support
- **Uvicorn**: ASGI server
- **Python 3.12**: Runtime
- **ChromaDB 0.4.22**: Vector database
- **OpenAI SDK 1.12.0+**: Azure OpenAI client
- **BeautifulSoup4 4.12.2**: HTML parsing
- **aiohttp 3.9.1**: Async HTTP client

### Frontend
- **Vanilla JavaScript**: No frameworks
- **Web Audio API**: AudioContext, AudioWorklet
- **WebSocket API**: Real-time bidirectional communication

### Azure Services
- **Azure OpenAI GPT-4o Realtime API**: Voice conversation
  - Endpoint: dsa-gpt4-dev.openai.azure.com
  - Deployment: gpt-realtime
  
- **Azure OpenAI Embeddings API**: Text embeddings
  - Endpoint: genai-varsha-dev.cognitiveservices.azure.com
  - Deployment: text-embedding-3-large
  - Dimensions: 3072

### Deployment (Planned)
- **GCP Cloud Run**: Containerized deployment
- **Docker**: Container packaging
- **Google Container Registry**: Image storage
- **Project**: vernac-479217

## Security Considerations

### API Keys
- Stored in `.env` (not committed to git)
- Environment variables in Cloud Run
- Separate keys for GPT-4 and embeddings

### CORS
- Configured allowed origins in `.env`
- Default: localhost:8003, 127.0.0.1:8003
- Production: Update to Cloud Run URL

### Rate Limiting
- Scraper: 2 second delay between requests
- Embedding: Batch processing (50 chunks)
- No user-facing rate limits (Azure handles)

### Data Privacy
- No PII stored in vector database
- Public help center content only
- Session data not persisted

## Scalability

### Current Limitations
- ChromaDB: In-memory/disk persistence (single instance)
- WebSocket: One connection per user (stateful)
- Scraper: Sequential crawling

### Future Improvements
- **ChromaDB**: Deploy as separate service with Cloud Storage persistence
- **Vector Store**: Use Pinecone or Weaviate for distributed search
- **Caching**: Redis for frequently asked questions
- **Load Balancing**: Multiple server instances with sticky sessions
- **Scraper**: Parallel crawling with worker pool

## Monitoring & Observability

### Logging
- Server: Python logging module (INFO level)
- Logs: Tool calls, search queries, errors
- Output: Console (stdout) and server.log

### Metrics (Planned)
- Requests per minute
- Average response latency
- Tool call success rate
- Vector search performance
- Error rate by type

### Health Checks
- `/health` endpoint
- Returns: `{"status": "ok", "service": "CXBuddy", "version": "1.0.0"}`

## Error Handling

### Client Errors
- Microphone permission denied → Alert user
- WebSocket disconnect → Auto-reconnect with exponential backoff
- Audio playback failure → Log and skip

### Server Errors
- Azure WebSocket failure → Log, close client connection
- Tool execution error → Return error message to Azure
- Vector store failure → Fallback to keyword search

### Fallback Strategy
```python
if USE_VECTOR_STORE and vector_store:
    result = vector_store.search(query)
else:
    result = keyword_search_fallback(query)  # Regex + scoring
```

## Performance Benchmarks

### Latency Breakdown
```
User speech → Response
├─ Audio capture: 0ms (streaming)
├─ WebSocket transfer: 20-50ms
├─ Azure transcription: 200-500ms
├─ Function call detection: 50-100ms
├─ Vector search: 150-250ms
│  ├─ Embedding: 100-200ms
│  └─ ChromaDB query: <50ms
├─ Response generation: 500-1000ms
└─ Audio playback: 0ms (streaming)
───────────────────────────────────
Total: 1.0-2.5 seconds
```

### Storage Requirements
- Knowledge base: ~500KB (200 pages)
- ChromaDB index: ~50MB (200 pages @ 3072 dims)
- Docker image: ~1.5GB (with dependencies)

## Development Workflow

### Local Development
```bash
# 1. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure .env
cp .env.example .env
# Add Azure credentials

# 3. Scrape knowledge base
python3 scraper.py

# 4. Start server
python3 server.py

# 5. Open browser
open http://localhost:8003
```

### Testing
```bash
# Test vector store
python3 test_vector_store.py

# Test embedding connection
python3 -c "from vector_store import GXSVectorStore; ..."
```

### Deployment
```bash
# Build Docker image
docker build -t cx-buddy .

# Test locally
docker run -p 8003:8003 --env-file .env cx-buddy

# Push to GCR
docker tag cx-buddy gcr.io/vernac-479217/cx-buddy
docker push gcr.io/vernac-479217/cx-buddy

# Deploy to Cloud Run
gcloud run deploy cx-buddy \
  --image gcr.io/vernac-479217/cx-buddy \
  --platform managed \
  --region us-central1 \
  --port 8003 \
  --memory 1Gi \
  --timeout 3600 \
  --set-env-vars-file .env.yaml
```

## Configuration Management

### Environment Variables
```bash
# Azure OpenAI (GPT-4 Realtime)
AZURE_OPENAI_ENDPOINT=yourendpoint
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_DEPLOYMENT=gpt-realtime

# Azure OpenAI (Embeddings)
AZURE_EMBEDDING_ENDPOINT= your endpoint
AZURE_EMBEDDING_API_KEY=xxx
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Server
HOST=0.0.0.0
PORT=8003

# Features
USE_VECTOR_STORE=true

# CORS
ALLOWED_ORIGINS=http://localhost:8003,http://127.0.0.1:8003
```

### Feature Flags
- `USE_VECTOR_STORE`: Enable/disable semantic search (falls back to keyword search)

## Disaster Recovery

### Backup Strategy
- **Knowledge Base**: Git-tracked (gxs_help_content/)
- **ChromaDB**: Backup chroma_db/ directory
- **Config**: Git-tracked (config.json)

### Recovery Procedure
```bash
# 1. Re-scrape knowledge base
python3 scraper.py

# 2. Rebuild vector store
python3 -c "
from vector_store import initialize_vector_store
initialize_vector_store(
    'gxs_help_content/gxs_help_consolidated.txt',
    force_reindex=True
)
"

# 3. Restart server
python3 server.py
```

## Future Architecture Enhancements

### Phase 2: Distributed Vector Store
```
ChromaDB → Pinecone/Weaviate
- Serverless vector search
- Auto-scaling
- Multi-region replication
```

### Phase 3: Multi-Language Support
```
- Language detection in Riley's system prompt
- Multi-lingual embeddings
- Separate knowledge bases per language
```

### Phase 4: Analytics Dashboard
```
- User query analytics
- Popular topics
- Unanswered questions
- Response quality metrics
```

### Phase 5: Continuous Learning
```
- Monitor Riley's responses
- Flag low-confidence answers
- Human review loop
- Retrain/update knowledge base
```
