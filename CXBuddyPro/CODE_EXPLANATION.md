# CXBuddy Code Explanation

This document provides a detailed walkthrough of the CXBuddy codebase, explaining the purpose and implementation of each major component.

## Table of Contents

1. [Server Implementation (server.py)](#server-implementation-serverpy)
2. [Vector Store (vector_store.py)](#vector-store-vector_storepy)
3. [Web Scraper (scraper.py)](#web-scraper-scraperpy)
4. [Frontend Client (client.js)](#frontend-client-clientjs)
5. [Audio Processing (audio-processor.js)](#audio-processing-audio-processorjs)
6. [Configuration (config.json)](#configuration-configjson)
7. [User Interface (index.html)](#user-interface-indexhtml)

---

## Server Implementation (server.py)

### Purpose
FastAPI WebSocket server that acts as a relay between the browser and Azure OpenAI Realtime API, with tool calling capabilities for knowledge base search.

### Key Components

#### 1. Initialization & Configuration
```python
# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Load Riley's configuration
with open('config.json', 'r') as f:
    CONFIG = json.load(f)
```

**Why**: Separation of secrets (`.env`) from configuration (`config.json`) allows secure credential management while keeping persona/behavior configurable.

#### 2. Knowledge Base Search Functions

##### Semantic Search (Vector Store)
```python
def search_knowledge_base(query: str) -> str:
    global vector_store
    
    if USE_VECTOR_STORE and vector_store is not None:
        logger.info(f"🔍 Semantic search: {query}")
        return vector_store.search(query, n_results=3)
    else:
        logger.info(f"🔍 Keyword search (fallback): {query}")
        return keyword_search_fallback(query)
```

**Why**: Semantic search understands meaning, not just keywords. Query "freeze my card" will match content about "temporarily stop usage" even without exact words.

**Fallback Strategy**: If vector store fails to initialize (missing dependencies, embedding API down), gracefully falls back to keyword search.

##### Keyword Search Fallback
```python
def keyword_search_fallback(query: str) -> str:
    import re
    
    # Extract keywords (remove stop words)
    words = re.findall(r'\b[a-z]+\b', query.lower())
    stop_words = {'are', 'the', 'is', 'a', 'and', ...}
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    # Score sections by keyword matches
    for section in sections:
        keyword_matches = sum(1 for kw in keywords if kw in section.lower())
        if keyword_matches > 0:
            score = keyword_matches * 100
            if keyword_matches == len(keywords):
                score += 200  # Bonus for all keywords present
            score = score / (section_len / 100)  # Favor shorter sections
```

**Why**: 
- **Stop word filtering**: Removes "are", "the", "is" to focus on meaningful terms
- **All-keywords bonus**: Sections with all query terms rank higher
- **Length normalization**: Short, focused sections (e.g., specific instructions) rank higher than long generic ones

**Example Scoring**:
```
Query: "how to freeze FlexiCard"
Keywords: ["freeze", "flexicard"]

Section A (317 chars): "You can freeze your GXS FlexiCard by..."
- keyword_matches: 2/2 ✓
- score: (2 * 100 + 200) / (317/100) = 400 / 3.17 = 126.2

Section B (1500 chars): "GXS FlexiCard is a credit card..."
- keyword_matches: 1/2 (only "flexicard")
- score: (1 * 100) / (1500/100) = 100 / 15 = 6.7

Section A ranks first! ✓
```

#### 3. System Instructions Builder
```python
def build_system_instructions() -> str:
    sp = CONFIG['system_prompt']
    
    instructions = f"""You are {sp['identity']}.

CRITICAL RULES (NON-NEGOTIABLE):
{chr(10).join(f"• {rule}" for rule in sp['core_rules'])}

CONVERSATION FLOW:
Phase 1 - Greeting & Personalization:
{sp['conversation_flow']['phase_1_greeting']}

Phase 2 - Answering Questions:
{sp['conversation_flow']['phase_2_answering']}

Edge Cases:
{sp['conversation_flow']['edge_cases']}
"""
    return instructions
```

**Why**: Dynamic instruction building allows easy persona updates without code changes. Just edit `config.json` and restart.

**Structure**:
- **Identity**: Who Riley is
- **Core Rules**: Non-negotiable behaviors (ALWAYS use tool, SYNTHESIZE don't read)
- **Conversation Flow**: Step-by-step guide for different interaction phases
- **Edge Cases**: Handling unknowns, out-of-scope questions

#### 4. Tool Call Handler
```python
async def handle_function_call(call_id: str, name: str, arguments: str):
    """Execute function call and return results to Azure"""
    logger.info(f"🔧 Function called: {name}")
    
    # Parse arguments
    args = json.loads(arguments)
    query = args.get('query', '')
    
    # Execute search
    result = search_knowledge_base(query)
    
    # Send results back to Azure
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
```

**Flow**:
```
1. Azure detects: "User wants to know about fees"
2. Azure decides: "I need search_gxs_help_center tool"
3. Azure sends: response.function_call_arguments.done
4. Server intercepts → Parses arguments → Executes search
5. Server sends: conversation.item.create with results
6. Server triggers: response.create
7. Azure generates: Natural language answer using search results
8. Azure streams: Audio response to user
```

**Why Async**: WebSocket operations are I/O-bound. `async/await` allows handling multiple concurrent connections efficiently.

#### 5. WebSocket Relay
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Connect to Azure OpenAI Realtime API
    azure_ws_url = f"{AZURE_ENDPOINT}/openai/realtime?api-version=2024-10-01-preview&deployment={AZURE_DEPLOYMENT}"
    
    async with websockets.connect(azure_ws_url, extra_headers={...}) as azure_ws:
        # Send session configuration
        await azure_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": CONFIG['voice'],
                "instructions": build_system_instructions(),
                "tools": CONFIG['tools'],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16"
            }
        }))
        
        # Bidirectional relay
        async def client_to_azure():
            async for message in websocket.iter_text():
                await azure_ws.send(message)
        
        async def azure_to_client():
            async for message in azure_ws:
                data = json.loads(message)
                
                # Intercept function calls
                if data['type'] == 'response.function_call_arguments.done':
                    await handle_function_call(
                        data['call_id'],
                        data['name'],
                        data['arguments']
                    )
                else:
                    # Forward to client
                    await websocket.send_text(message)
        
        # Run both directions concurrently
        await asyncio.gather(client_to_azure(), azure_to_client())
```

**Why Two Coroutines**: 
- `client_to_azure()`: Streams user audio to Azure
- `azure_to_client()`: Streams Azure responses to client
- Both run concurrently via `asyncio.gather()`

**Interception Point**: `response.function_call_arguments.done` is where we intercept, execute the search, and inject results back into the conversation.

#### 6. Server Startup
```python
if __name__ == "__main__":
    # Initialize vector store
    if USE_VECTOR_STORE:
        initialize_vector_store(
            knowledge_file=KNOWLEDGE_BASE_PATH,
            force_reindex=False,
            azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
            azure_api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
            embedding_deployment=EMBEDDING_DEPLOYMENT
        )
    
    # Start server
    uvicorn.run(app, host=HOST, port=PORT)
```

**Initialization Order**:
1. Load environment variables
2. Load config.json
3. Initialize vector store (if enabled)
4. Start FastAPI/Uvicorn server

**Why Load Vector Store on Startup**: Embedding and indexing take 2-5 minutes. Better to do once at startup than on first request.

---

## Vector Store (vector_store.py)

### Purpose
Semantic search over GXS help content using ChromaDB and Azure OpenAI embeddings.

### Class: GXSVectorStore

#### 1. Initialization
```python
def __init__(self, persist_directory="./chroma_db", collection_name="gxs_help_center", ...):
    # Initialize Azure OpenAI client for embeddings
    self.azure_client = AzureOpenAI(
        api_key=azure_api_key or os.getenv("AZURE_EMBEDDING_API_KEY"),
        api_version="2023-05-15",
        azure_endpoint=azure_endpoint or os.getenv("AZURE_EMBEDDING_ENDPOINT")
    )
    
    # Initialize ChromaDB
    self.chroma_client = chromadb.PersistentClient(
        path=persist_directory,
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    
    # Get or create collection
    self.collection = self.chroma_client.get_collection(name=collection_name)
```

**Why PersistentClient**: Stores vectors on disk (`./chroma_db/`). Survives server restarts without re-indexing.

**Why Separate Embedding Endpoint**: Different Azure OpenAI resource optimized for embeddings (genai-varsha-dev) vs. chat (dsa-gpt4-dev).

#### 2. Text Chunking
```python
def chunk_text(self, text: str, chunk_size=500, overlap=100) -> List[str]:
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            last_100 = text[max(start, end-100):end]
            for delimiter in ['. ', '? ', '! ', '\n\n']:
                last_delim = last_100.rfind(delimiter)
                if last_delim != -1:
                    end = max(start, end-100) + last_delim + len(delimiter)
                    break
        
        chunk = text[start:end].strip()
        chunks.append(chunk)
        start = end - overlap  # Overlap ensures context continuity
```

**Why Chunking**:
- **Embedding limits**: Models have token limits (~8000 tokens)
- **Retrieval precision**: Smaller chunks = more precise matches
- **Context preservation**: Overlap ensures important info isn't split

**Smart Boundary Detection**:
```
Text: "...freeze your card. Here's how: 1. Log in to app. 2. Tap freeze..."
      
Chunk 1: "...freeze your card. Here's how: 1. Log in to app."
                                   ↑ Break at sentence
Overlap: "1. Log in to app. 2. Tap freeze..."
Chunk 2: "1. Log in to app. 2. Tap freeze..."
```

#### 3. Embedding Generation
```python
def get_embedding(self, text: str) -> List[float]:
    response = self.azure_client.embeddings.create(
        input=text,
        model=self.embedding_deployment
    )
    return response.data[0].embedding  # 3072-dim vector
```

**What is an Embedding?**
```
Text: "How do I freeze my FlexiCard?"
         ↓ (text-embedding-3-large)
Vector: [-0.031, 0.002, -0.011, 0.010, 0.047, ..., 0.019]
        └─────────────────── 3072 dimensions ──────────────────┘

Meaning captured in high-dimensional space!
```

**Why text-embedding-3-large**:
- 3072 dimensions (vs. 1536 for ada-002)
- Better semantic understanding
- Higher quality retrieval

#### 4. Indexing
```python
def index_knowledge_base(self, knowledge_file: str, force_reindex=False):
    # Load content
    with open(knowledge_file, 'r') as f:
        content = f.read()
    
    # Split into sections (by page breaks)
    sections = content.split('=' * 100)
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    for section_idx, section in enumerate(sections):
        # Extract metadata
        source = extract_source(section)  # URL
        title = extract_title(section)    # Page title
        
        # Chunk section
        chunks = self.chunk_text(section, chunk_size=500, overlap=100)
        
        for chunk_idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadatas.append({
                "source": source,
                "title": title,
                "section_id": section_idx,
                "chunk_id": chunk_idx
            })
            all_ids.append(f"chunk_{chunk_id}")
    
    # Batch embed and add to ChromaDB
    for i in range(0, len(all_chunks), batch_size=50):
        batch_chunks = all_chunks[i:i+50]
        batch_embeddings = [self.get_embedding(chunk) for chunk in batch_chunks]
        
        self.collection.add(
            documents=batch_chunks,
            embeddings=batch_embeddings,
            metadatas=all_metadatas[i:i+50],
            ids=all_ids[i:i+50]
        )
```

**Batching Strategy**: Process 50 chunks at a time to balance memory usage and API rate limits.

**Metadata Purpose**: Attach source URL and title to each chunk for citation.

#### 5. Semantic Search
```python
def search(self, query: str, n_results=3) -> str:
    # Get query embedding
    query_embedding = self.get_embedding(query)
    
    # Search ChromaDB (cosine similarity)
    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results * 2  # Get extras for deduplication
    )
    
    # Deduplicate and format
    unique_results = []
    seen_content = set()
    
    for i, doc in enumerate(results['documents'][0]):
        if doc not in seen_content:
            metadata = results['metadatas'][0][i]
            result_text = f"[{metadata['title']}]\n{doc}"
            unique_results.append(result_text)
        
        if len(unique_results) >= n_results:
            break
    
    return '\n\n---\n\n'.join(unique_results)
```

**Cosine Similarity**:
```
Query vector:  [0.1, 0.5, 0.3, ...]
Chunk vector:  [0.2, 0.4, 0.3, ...]
               ↓ Calculate angle between vectors
Similarity score: 0.92 (0-1 scale, higher = more similar)
```

**Deduplication**: Same content might appear in multiple chunks due to overlap. Keep only unique results.

---

## Web Scraper (scraper.py)

### Purpose
Crawl help.gxs.com.sg and extract help center content for embedding into vector store.

### Class: GXSHelpScraper

#### 1. Configuration
```python
def __init__(self, base_url="https://help.gxs.com.sg", max_pages=200, delay=2.0):
    self.base_url = base_url
    self.max_pages = max_pages
    self.delay = delay  # Respectful crawling
    self.visited_urls = set()
    self.queue = deque([base_url])
```

**Why BFS (Breadth-First Search)**:
```
Level 0: help.gxs.com.sg/
Level 1: ├─ /GXS_FlexiCard
         ├─ /GXS_Savings_Account
         └─ /Emergencies
Level 2: ├─ /GXS_FlexiCard/How_to_apply
         ├─ /GXS_FlexiCard/Fees
         └─ ...
```
BFS visits all main category pages before going deep into sub-pages. Ensures comprehensive coverage.

**Why 2-second delay**: Respectful to GXS servers. Avoids being rate-limited or blocked.

#### 2. Content Extraction
```python
def extract_text_content(self, soup, url):
    # Remove navigation, footer, etc.
    for tag in soup(['nav', 'footer', 'script', 'style']):
        tag.decompose()
    
    # Extract title
    title = soup.find('h1')
    title_text = title.get_text(strip=True) if title else "Untitled"
    
    # Extract main content
    text = soup.get_text(separator='\n', strip=True)
    
    # Clean whitespace
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    
    # Validate minimum word count
    word_count = len(text.split())
    if word_count < 20:
        logger.info(f"⚠ Skipped (too short): {title_text} ({word_count} words)")
        return None
    
    # Format with metadata
    content = f"""SOURCE: {url}
TITLE: {title_text}

{text}
"""
    return content, title_text, word_count
```

**Why Remove nav/footer**: Navigation menus and footers add noise. We only want actual help content.

**Why 20-word minimum**: Filter out empty pages, navigation-only pages, or error pages.

**Metadata Format**:
```
SOURCE: https://help.gxs.com.sg/GXS_FlexiCard/How_to_freeze
TITLE: How to freeze your GXS FlexiCard

You can temporarily stop usage of your GXS FlexiCard by freezing it...
```

Later, vector store extracts this metadata for citations.

#### 3. Crawling Logic
```python
def crawl(self):
    while self.queue and len(self.visited_urls) < self.max_pages:
        url = self.queue.popleft()
        
        if url in self.visited_urls:
            continue
        
        # Fetch page
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract content
        content = self.extract_text_content(soup, url)
        if content:
            self.pages.append(content)
        
        # Find links
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            
            # Only follow same-domain links
            if full_url.startswith(self.base_url):
                if full_url not in self.visited_urls:
                    self.queue.append(full_url)
        
        self.visited_urls.add(url)
        time.sleep(self.delay)  # Be nice to server
```

**Queue Management**:
```
queue = [homepage]
      ↓ Visit homepage
queue = [link1, link2, link3]
      ↓ Visit link1
queue = [link2, link3, link1_sublink1, link1_sublink2]
      ↓ Visit link2
...
```

**Same-Domain Filter**: Only crawl help.gxs.com.sg, not external links (e.g., gxs.com.sg homepage, Facebook).

#### 4. Output
```python
def save_to_files(self, output_dir="gxs_help_content"):
    os.makedirs(output_dir, exist_ok=True)
    
    # Save individual pages
    for i, (content, title, word_count) in enumerate(self.pages, 1):
        filename = f"page_{i:03d}_{sanitize_filename(title)}.txt"
        with open(os.path.join(output_dir, filename), 'w') as f:
            f.write(content)
    
    # Save consolidated file
    consolidated = '\n\n' + '=' * 100 + '\n\n'.join(
        content for content, _, _ in self.pages
    )
    with open(os.path.join(output_dir, 'gxs_help_consolidated.txt'), 'w') as f:
        f.write(consolidated)
    
    # Save metadata
    metadata = {
        "pages_scraped": len(self.pages),
        "total_words": sum(wc for _, _, wc in self.pages),
        "scrape_date": datetime.now().isoformat()
    }
    with open(os.path.join(output_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
```

**Why Three Files**:
1. **Individual pages**: Easy to inspect specific articles
2. **Consolidated file**: Single file for vector store indexing
3. **Metadata**: Track scraping stats, useful for monitoring changes

---

## Frontend Client (client.js)

### Purpose
Browser WebSocket client that captures microphone audio, streams to server, and plays back responses.

### Class: RealtimeClient

#### 1. Initialization
```python
constructor(serverUrl) {
    this.serverUrl = serverUrl;
    this.ws = null;
    this.audioContext = null;
    this.audioWorklet = null;
    this.mediaStream = null;
    this.isRecording = false;
    
    // UI elements
    this.startBtn = document.getElementById('startBtn');
    this.endBtn = document.getElementById('endBtn');
    this.status = document.getElementById('status');
    this.transcript = document.getElementById('transcript');
}
```

**Why Class-Based**: Encapsulates all client logic in a single reusable component.

#### 2. WebSocket Connection
```python
async startCall() {
    // Request microphone permission
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            sampleRate: 24000,
            channelCount: 1,  // Mono
            echoCancellation: true,
            noiseSuppression: true
        }
    });
    
    // Create AudioContext
    this.audioContext = new AudioContext({ sampleRate: 24000 });
    
    // Load AudioWorklet processor
    await this.audioContext.audioWorklet.addModule('audio-processor.js');
    
    // Connect microphone to worklet
    const source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.audioWorklet = new AudioWorkletNode(this.audioContext, 'audio-processor');
    source.connect(this.audioWorklet);
    
    // WebSocket connection
    this.ws = new WebSocket(this.serverUrl);
    
    this.ws.onopen = () => {
        this.updateStatus('connected', 'Connected - Listening');
        this.isRecording = true;
    };
    
    this.ws.onmessage = (event) => {
        this.handleServerMessage(JSON.parse(event.data));
    };
}
```

**Audio Pipeline**:
```
Microphone → MediaStream → AudioContext → AudioWorklet → WebSocket → Server
                                                ↑
                                          Process audio:
                                          - Resample to 24kHz
                                          - Convert to PCM16
                                          - Base64 encode
```

**Why AudioWorklet**: Runs audio processing in a separate thread (not main thread). Prevents UI blocking and audio glitches.

#### 3. Audio Streaming
```python
// In audio-processor.js (AudioWorklet)
class AudioProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || !input[0]) return true;
        
        const samples = input[0];  // Float32Array [-1.0 to 1.0]
        
        // Convert to PCM16 (Int16Array)
        const pcm16 = new Int16Array(samples.length);
        for (let i = 0; i < samples.length; i++) {
            const s = Math.max(-1, Math.min(1, samples[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Send to main thread
        this.port.postMessage(pcm16.buffer);
        
        return true;  // Keep processor alive
    }
}
```

**Why PCM16**: Azure OpenAI Realtime API expects signed 16-bit PCM audio. 

**Float32 → Int16 Conversion**:
```
Float:  -1.0  →  0.0  →  1.0
Int16: -32768 →   0   → 32767
```

#### 4. Response Handling
```python
handleServerMessage(data) {
    switch (data.type) {
        case 'response.audio.delta':
            // Audio chunk from Azure
            this.playAudioChunk(data.delta);  // Base64 PCM16
            break;
        
        case 'conversation.item.created':
            // Transcript update
            if (data.item.type === 'message') {
                this.addTranscript(data.item.role, data.item.content[0].transcript);
            }
            break;
        
        case 'response.done':
            // Response complete
            this.log('✓ Response complete');
            break;
        
        case 'error':
            this.log(`❌ Error: ${data.error.message}`);
            break;
    }
}
```

**Event Types**:
- `response.audio.delta`: Streaming audio chunks (Azure → Client)
- `conversation.item.created`: Transcript update (user speech recognized)
- `response.done`: Azure finished speaking
- `error`: Something went wrong

#### 5. Audio Playback
```python
async playAudioChunk(base64Audio) {
    // Decode base64 to ArrayBuffer
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    
    // Convert PCM16 to Float32
    const pcm16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7FFF);
    }
    
    // Create AudioBuffer
    const audioBuffer = this.audioContext.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);
    
    // Play
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);
    source.start();
}
```

**Playback Pipeline**:
```
Base64 → Decode → PCM16 → Float32 → AudioBuffer → BufferSource → Speakers
```

---

## Configuration (config.json)

### Structure Breakdown

#### 1. Voice & Identity
```json
{
    "voice": "shimmer",
    "agent_name": "Riley",
    "intro_message": "Hi there! I'm Riley, your friendly GXS Bank guide..."
}
```

**Available Voices**: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

**Why Shimmer**: Friendly, warm, approachable female voice. Fits customer service persona.

#### 2. System Prompt
```json
{
    "system_prompt": {
        "identity": "You are Riley, a GXS Customer Experience Specialist...",
        "core_rules": [
            "ALWAYS USE THE TOOL for any GXS product/service questions",
            "SYNTHESIZE DON'T READ - Use natural language",
            "HANDLE LATENCY - Acknowledge search is happening"
        ],
        "conversation_flow": {...}
    }
}
```

**Core Rules**:
- **ALWAYS USE THE TOOL**: Prevents hallucination. Riley must search, not guess.
- **SYNTHESIZE DON'T READ**: Transform "1. Log in to app. 2. Tap freeze." into "Just log in to the GXS Bank app, go to your FlexiCard screen, and tap freeze!"
- **HANDLE LATENCY**: Say "Let me check that for you" during 200-300ms search delay

#### 3. Tools Definition
```json
{
    "tools": [{
        "type": "function",
        "name": "search_gxs_help_center",
        "description": "REQUIRED: Use this tool to look up information about GXS Bank products...",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's question or search query"
                }
            },
            "required": ["query"]
        }
    }]
}
```

**Why JSON Schema**: Azure OpenAI uses schema to understand when/how to call the function.

**Description Importance**: "REQUIRED: Use this tool..." in description prompts Azure to call the function instead of hallucinating answers.

---

## User Interface (index.html)

### Design Principles

#### 1. GXS Branding
```css
background: linear-gradient(135deg, #6b46c1 0%, #805ad5 50%, #9f7aea 100%);
/* Purple gradient matching GXS Bank brand */

.header {
    background: linear-gradient(135deg, #6b46c1, #805ad5);
    /* Darker purple for header */
}
```

**Color Palette**:
- **Primary**: #6b46c1 (Purple)
- **Secondary**: #805ad5 (Light Purple)
- **Accent**: #9f7aea (Lavender)

**Why Purple**: Matches GXS Bank's brand identity (trust, innovation, premium service).

#### 2. Button Design
```css
#startBtn {
    background: linear-gradient(135deg, #6b46c1 0%, #805ad5 100%);
    color: white;
}

#endBtn {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
}
```

**Visual Feedback**:
```css
button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(107, 70, 193, 0.4);
}
```

Subtle lift on hover creates interactive feel.

#### 3. Transcript Display
```html
<div id="transcript">
    <div class="transcript-item">
        <div class="transcript-role riley">Riley</div>
        <div class="transcript-text">Hi there! I'm Riley...</div>
    </div>
    <div class="transcript-item">
        <div class="transcript-role user">You</div>
        <div class="transcript-text">How do I freeze my card?</div>
    </div>
</div>
```

**Role Colors**:
- **Riley**: Purple (#6b46c1) - matches brand
- **User**: Green (#4ade80) - contrasts for clarity

**Why Transcript**: Users can review conversation, especially useful for complex instructions.

---

## Data Flow Summary

### Complete User Interaction
```
1. User clicks "Start Call"
   ↓
2. Browser requests microphone permission
   ↓
3. WebSocket connects to server
   ↓
4. Server connects to Azure OpenAI Realtime API
   ↓
5. Audio pipeline starts:
   Mic → AudioWorklet → PCM16 → WebSocket → Server → Azure
   ↓
6. User speaks: "How do I freeze my FlexiCard?"
   ↓
7. Azure transcribes speech
   ↓
8. Azure detects need for search_gxs_help_center
   ↓
9. Azure sends: response.function_call_arguments.done
   ↓
10. Server intercepts → Calls vector_store.search()
    ↓
11. Vector store:
    a. Embeds query: "how to freeze flexicard" → [0.03, -0.01, ...]
    b. ChromaDB similarity search
    c. Returns top 3 chunks with freeze instructions
    ↓
12. Server sends results back to Azure
    ↓
13. Azure generates natural response:
    "Sure! To freeze your FlexiCard, just log in to the GXS Bank app..."
    ↓
14. Azure streams audio response
    ↓
15. Server relays to browser
    ↓
16. Browser plays audio + updates transcript
    ↓
17. User hears Riley's answer!
```

**Latency**: 1.0-2.5 seconds total (speech → response)

---

## Error Handling Strategies

### 1. Graceful Degradation
```python
# If vector store fails, fall back to keyword search
if USE_VECTOR_STORE and vector_store:
    result = vector_store.search(query)
else:
    result = keyword_search_fallback(query)
```

### 2. Null Checks
```javascript
if (this.startBtn) {
    this.startBtn.addEventListener('click', () => this.startCall());
}
```

Prevents crashes if HTML structure changes.

### 3. Try-Catch Wrappers
```python
try:
    result = search_knowledge_base(query)
except Exception as e:
    logger.error(f"Search failed: {e}")
    result = "I'm having trouble accessing the knowledge base. Please try again."
```

### 4. User-Friendly Messages
Instead of:
```
Error: ChromaDB collection not found
```

Show:
```
I'm having trouble finding that information right now. Let me connect you to a human agent.
```

---

## Performance Optimizations

### 1. Batch Embedding
```python
# Bad: One API call per chunk (slow!)
for chunk in chunks:
    embedding = get_embedding(chunk)

# Good: Batch 50 chunks per API call
for i in range(0, len(chunks), 50):
    batch = chunks[i:i+50]
    embeddings = [get_embedding(c) for c in batch]
```

### 2. ChromaDB Persistence
```python
# Persistent storage = no re-indexing on restart
chroma_client = chromadb.PersistentClient(path="./chroma_db")
```

### 3. Async WebSocket Relay
```python
# Concurrent bidirectional streaming
await asyncio.gather(client_to_azure(), azure_to_client())
```

### 4. Audio Worklet Thread
```javascript
// Audio processing in separate thread
await audioContext.audioWorklet.addModule('audio-processor.js');
```

---

## Security Considerations

### 1. Environment Variables
```python
# .env file (not in git)
AZURE_OPENAI_API_KEY=xxx

# Load securely
load_dotenv()
api_key = os.getenv("AZURE_OPENAI_API_KEY")
```

### 2. CORS Protection
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8003").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Input Validation
```python
# Validate query parameter
if not query or len(query) > 500:
    return "Invalid query"
```

---

## Testing Strategies

### 1. Unit Tests
```python
# Test vector store search
def test_search():
    store = GXSVectorStore(...)
    result = store.search("freeze card")
    assert "freeze" in result.lower()
```

### 2. Integration Tests
```python
# Test full pipeline
async def test_tool_calling():
    # Send query → Check function call → Verify results
```

### 3. Manual Testing
```bash
# Test vector store
python3 test_vector_store.py

# Test embedding connection
python3 -c "from vector_store import GXSVectorStore; ..."
```

---

## Deployment Checklist

- [ ] Update `.env` with production credentials
- [ ] Set `ALLOWED_ORIGINS` to Cloud Run URL
- [ ] Run scraper to get latest help content
- [ ] Index vector store (`force_reindex=True`)
- [ ] Test locally with `python3 server.py`
- [ ] Build Docker image
- [ ] Push to Google Container Registry
- [ ] Deploy to Cloud Run
- [ ] Test production URL
- [ ] Monitor logs for errors

---

**End of Code Explanation**
