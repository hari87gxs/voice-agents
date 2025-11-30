# CXBuddy - GXS Bank Voice Agent

A voice-enabled AI customer service agent for GXS Bank, built with Azure OpenAI Realtime API and ChromaDB vector search.

## Quick Start

### Prerequisites
- Python 3.9+
- Azure OpenAI API access (GPT-4o Realtime + text-embedding-3-large)
- Google Cloud SDK (for deployment)

### Installation

1. **Clone and navigate to project**
   ```bash
   cd /Users/hari/Documents/haricode/CXBuddy
   ```

2. **Install dependencies**
   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file with the following:
   ```bash
   # Azure OpenAI - GPT-4 Realtime API
   AZURE_OPENAI_ENDPOINT=https://dsa-gpt4-dev.openai.azure.com/
   AZURE_OPENAI_API_KEY=your_gpt4_api_key
   AZURE_OPENAI_DEPLOYMENT=gpt-realtime

   # Azure OpenAI - Embeddings API (separate endpoint)
   AZURE_EMBEDDING_ENDPOINT=https://genai-varsha-dev.cognitiveservices.azure.com/
   AZURE_EMBEDDING_API_KEY=your_embedding_api_key
   AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large

   # Server Configuration
   HOST=0.0.0.0
   PORT=8003
   USE_VECTOR_STORE=true

   # GCP Configuration
   GCP_PROJECT_ID=vernac-479217
   ```

4. **Run locally**
   ```bash
   python3 server.py
   ```

5. **Open in browser**
   ```
   http://localhost:8003
   ```

---

## Updating the Knowledge Base

The knowledge base is built from the GXS Bank help center (help.gxs.com.sg). When help center content changes, follow these steps to update Riley's knowledge.

### When to Update

Update the knowledge base when:
- ✅ New products are launched (e.g., new credit cards, loan products)
- ✅ Help articles are added or updated
- ✅ FAQ content changes
- ✅ Policies or procedures are modified
- ✅ Promotional campaigns start/end

**Recommended frequency**: Weekly or after major product launches

---

## Step-by-Step Update Guide

### Step 1: Scrape Updated Content

The scraper crawls help.gxs.com.sg and extracts all help articles.

```bash
# Run the scraper
python3 scraper.py
```

**What it does:**
- Crawls up to 200 pages from help.gxs.com.sg
- Extracts text content (minimum 20 words per page)
- Saves to `gxs_help_content/` directory
- Creates consolidated file: `gxs_help_consolidated.txt`
- Generates metadata: `metadata.json`

**Expected output:**
```
✓ Extracted 171 pages
✓ Total words: 22,386
✓ Saved to gxs_help_content/
```

**Time estimate**: 6-10 minutes (200 pages × 2 second delay)

**Configuration** (edit `scraper.py` if needed):
```python
scraper = GXSHelpScraper(
    base_url="https://help.gxs.com.sg/",
    max_pages=200,        # Max pages to crawl
    delay=2.0,            # Delay between requests (seconds)
    min_words=20          # Minimum words per page
)
```

---

### Step 2: Rebuild Vector Store Index

After scraping, rebuild the vector store to embed the new content.

```bash
# Run indexing (this will take 10-15 minutes)
python3 -c "
from vector_store import GXSVectorStore
import os
from dotenv import load_dotenv

load_dotenv()

store = GXSVectorStore(
    persist_directory='./chroma_db',
    collection_name='gxs_help_center',
    azure_endpoint=os.getenv('AZURE_EMBEDDING_ENDPOINT'),
    azure_api_key=os.getenv('AZURE_EMBEDDING_API_KEY'),
    embedding_deployment=os.getenv('AZURE_EMBEDDING_DEPLOYMENT')
)

store.index_knowledge_base(
    knowledge_file='gxs_help_content/gxs_help_consolidated.txt',
    force_reindex=True  # Force rebuild
)

print('✅ Vector store updated successfully!')
print(store.get_stats())
"
```

**What it does:**
- Loads `gxs_help_consolidated.txt`
- Chunks text into 500-character segments (100-char overlap)
- Generates embeddings using text-embedding-3-large (3072 dimensions)
- Stores vectors in ChromaDB (`./chroma_db/`)
- Batch processes 50 chunks at a time

**Expected output:**
```
✅ Indexed 450 chunks
✅ Vector store updated successfully!
{
  "collection_name": "gxs_help_center",
  "total_documents": 450,
  "persist_directory": "./chroma_db",
  "embedding_model": "text-embedding-3-large"
}
```

**Time estimate**: 10-15 minutes for 171 pages (~450 chunks)

**Cost estimate**: ~$0.50-1.00 (text-embedding-3-large pricing)

---

### Step 3: Verify Search Quality

Test the updated vector store with sample queries.

```bash
python3 test_vector_store.py
```

Or test interactively:

```python
from vector_store import GXSVectorStore
import os
from dotenv import load_dotenv

load_dotenv()

store = GXSVectorStore(
    persist_directory='./chroma_db',
    collection_name='gxs_help_center',
    azure_endpoint=os.getenv('AZURE_EMBEDDING_ENDPOINT'),
    azure_api_key=os.getenv('AZURE_EMBEDDING_API_KEY'),
    embedding_deployment=os.getenv('AZURE_EMBEDDING_DEPLOYMENT')
)

# Test queries
queries = [
    "How do I freeze my FlexiCard?",
    "What are the interest rates for savings?",
    "How do I report a lost card?",
    "What are the fees for GXS FlexiCard?"
]

for query in queries:
    print(f"\n📝 Query: {query}")
    result = store.search(query, n_results=3)
    print(f"📊 Result: {result[:200]}...")
```

**Expected behavior:**
- Queries return relevant help articles
- Top results match the topic
- Citations include source URLs and titles

---

### Step 4: Restart Server

After updating the vector store, restart the server to load the new index.

```bash
# Stop current server (Ctrl+C or kill process)
lsof -ti:8003 | xargs kill -9

# Restart with updated vector store
python3 server.py
```

**What happens on startup:**
- Server loads ChromaDB from `./chroma_db/`
- Connects to Azure embedding endpoint
- Initializes vector store (no re-indexing needed)
- Ready to serve updated knowledge

**Startup time**: ~5-10 seconds

---

### Step 5: Test End-to-End

1. **Open browser**: http://localhost:8003
2. **Click "Start Call"**
3. **Ask test questions**:
   - "How do I freeze my FlexiCard?"
   - "What are the savings account interest rates?"
   - "How do I report fraud?"
4. **Verify Riley's answers** match latest help center content

---

## Troubleshooting

### Issue: Scraper fails with "Connection timeout"

**Solution**: help.gxs.com.sg might be rate-limiting. Increase delay:
```python
scraper = GXSHelpScraper(delay=5.0)  # 5 seconds between requests
```

---

### Issue: Embedding API returns 404 "DeploymentNotFound"

**Solution**: Check that you're using the **AZURE_EMBEDDING_ENDPOINT** (not AZURE_OPENAI_ENDPOINT):
```bash
# Correct endpoint for embeddings
AZURE_EMBEDDING_ENDPOINT=https://genai-varsha-dev.cognitiveservices.azure.com/
```

---

### Issue: Vector store search returns irrelevant results

**Solutions**:
1. **Re-scrape with lower min_words**: Might have missed short but important pages
   ```python
   scraper = GXSHelpScraper(min_words=15)
   ```

2. **Check chunking strategy**: Verify chunks aren't too small or large
   ```python
   store.chunk_text(text, chunk_size=500, overlap=100)
   ```

3. **Increase search results**: Get more candidates before deduplication
   ```python
   result = store.search(query, n_results=5)  # Get top 5
   ```

---

### Issue: "ChromaDB collection not found"

**Solution**: Vector store not initialized. Run Step 2 (rebuild index).

---

### Issue: Server falls back to keyword search

**Symptoms**: Logs show "🔍 Keyword search (fallback)" instead of "🔍 Semantic search"

**Solutions**:
1. Check `USE_VECTOR_STORE=true` in `.env`
2. Verify `./chroma_db/` directory exists
3. Check embedding API credentials
4. Review server startup logs for errors

---

## Monitoring & Maintenance

### Check Knowledge Base Stats

```python
from vector_store import GXSVectorStore
store = GXSVectorStore()
print(store.get_stats())
```

**Output:**
```json
{
  "collection_name": "gxs_help_center",
  "total_documents": 450,
  "persist_directory": "./chroma_db",
  "embedding_model": "text-embedding-3-large",
  "last_updated": "2025-11-28T00:44:01"
}
```

---

### Review Scraper Metadata

```bash
cat gxs_help_content/metadata.json
```

**Output:**
```json
{
  "scraped_at": "2025-11-28T00:44:01.733511",
  "base_url": "https://help.gxs.com.sg/",
  "pages_scraped": 171,
  "total_words": 22386
}
```

Track changes over time:
- **pages_scraped**: Should increase when new help articles added
- **total_words**: Indicates content volume
- **scraped_at**: Last update timestamp

---

### Monitor Search Latency

Check server logs for performance:
```bash
tail -f server.log | grep "Semantic search"
```

**Expected latency**:
- Embedding generation: 100-200ms
- ChromaDB search: 50-100ms
- Total search: 150-300ms

If latency exceeds 500ms, consider:
- Reducing `n_results` parameter
- Optimizing chunk size
- Upgrading to distributed vector store (Pinecone/Weaviate)

---

## Advanced Configuration

### Custom Chunking Strategy

Edit `vector_store.py` to adjust chunking:

```python
def chunk_text(self, text: str, chunk_size=500, overlap=100):
    # Smaller chunks = more precise matches, more API calls
    # Larger chunks = more context, fewer API calls
    
    # For short FAQ answers:
    chunk_size = 300, overlap = 50
    
    # For long articles:
    chunk_size = 800, overlap = 150
```

---

### Batch Size for Indexing

Adjust batch size in `index_knowledge_base()`:

```python
# Default: 50 chunks per batch
for i in range(0, len(all_chunks), 50):
    batch = all_chunks[i:i+50]
    
# For faster indexing (higher API rate limits):
for i in range(0, len(all_chunks), 100):
    batch = all_chunks[i:i+100]
```

---

### Search Result Tuning

Adjust search parameters in `server.py`:

```python
def search_knowledge_base(query: str) -> str:
    # Get more results (default: 3)
    result = vector_store.search(query, n_results=5)
    
    # Filter by similarity threshold (requires ChromaDB modification)
    # Only return results with cosine similarity > 0.7
```

---

## Backup & Recovery

### Backup Knowledge Base

```bash
# Backup scraped content
tar -czf gxs_backup_$(date +%Y%m%d).tar.gz gxs_help_content/

# Backup vector store
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/
```

---

### Restore from Backup

```bash
# Restore scraped content
tar -xzf gxs_backup_20251128.tar.gz

# Restore vector store
tar -xzf chroma_backup_20251128.tar.gz
```

---

### Disaster Recovery

If vector store is corrupted:

1. **Delete corrupted ChromaDB**:
   ```bash
   rm -rf chroma_db/
   ```

2. **Re-index from backup content**:
   ```bash
   python3 -c "from vector_store import GXSVectorStore; store = GXSVectorStore(); store.index_knowledge_base('gxs_help_content/gxs_help_consolidated.txt', force_reindex=True)"
   ```

3. **Verify**:
   ```bash
   python3 test_vector_store.py
   ```

---

## Production Deployment

### Deploy to Cloud Run

1. **Update Dockerfile** to include ChromaDB:
   ```dockerfile
   COPY chroma_db/ ./chroma_db/
   COPY gxs_help_content/ ./gxs_help_content/
   ```

2. **Build and deploy**:
   ```bash
   gcloud builds submit --tag gcr.io/vernac-479217/cx-buddy
   
   source .env && gcloud run deploy cx-buddy \
     --image gcr.io/vernac-479217/cx-buddy \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT,AZURE_EMBEDDING_ENDPOINT=$AZURE_EMBEDDING_ENDPOINT,AZURE_EMBEDDING_API_KEY=$AZURE_EMBEDDING_API_KEY,AZURE_EMBEDDING_DEPLOYMENT=$AZURE_EMBEDDING_DEPLOYMENT,USE_VECTOR_STORE=true \
     --port 8003 \
     --memory 1Gi \
     --cpu 1 \
     --timeout 3600
   ```

**Note**: Memory increased to 1Gi for ChromaDB.

---

### Update Production Knowledge Base

For zero-downtime updates:

1. **Scrape locally** (dev environment)
2. **Test vector store** with new content
3. **Deploy new Docker image** with updated `chroma_db/`
4. Cloud Run auto-scales and deploys new instances

---

## Performance Benchmarks

| Operation | Latency | Notes |
|-----------|---------|-------|
| Scraping (200 pages) | 6-10 min | 2s delay between requests |
| Indexing (171 pages) | 10-15 min | 450 chunks, 50 batch size |
| Embedding generation | 100-200ms | text-embedding-3-large API call |
| Vector search | 50-100ms | ChromaDB cosine similarity |
| Total search latency | 150-300ms | Embedding + search |
| Full conversation turn | 1.0-2.5s | Transcription + search + response |

---

## Cost Estimates

### Embedding Costs (text-embedding-3-large)

| Operation | Input Tokens | Cost (at $0.13/1M tokens) |
|-----------|--------------|---------------------------|
| Initial indexing (22,386 words) | ~30,000 | $0.0039 |
| Single query embedding | ~10 | $0.000001 |
| Daily usage (100 queries) | ~1,000 | $0.00013 |
| Monthly (3,000 queries) | ~30,000 | $0.0039 |

**Total monthly cost**: ~$0.01 (embeddings) + GPT-4o Realtime API usage

---

## Support & Documentation

- **Architecture**: See `ARCHITECTURE.md` for system design
- **Code Explanation**: See `CODE_EXPLANATION.md` for detailed code walkthrough
- **API Docs**: See Azure OpenAI Realtime API documentation

---

## Changelog

### 2025-11-28
- ✅ Initial scraper implementation (200 pages, 171 extracted)
- ✅ ChromaDB vector store integration
- ✅ Azure text-embedding-3-large (3072 dimensions)
- ✅ Riley persona configuration
- ✅ GXS purple branding

---

## Quick Reference Commands

```bash
# Scrape help center
python3 scraper.py

# Rebuild vector store
python3 -c "from vector_store import GXSVectorStore; store = GXSVectorStore(); store.index_knowledge_base('gxs_help_content/gxs_help_consolidated.txt', force_reindex=True)"

# Test vector store
python3 test_vector_store.py

# Run server
python3 server.py

# Check scraper stats
cat gxs_help_content/metadata.json

# Check vector store stats
python3 -c "from vector_store import GXSVectorStore; print(GXSVectorStore().get_stats())"

# Backup knowledge base
tar -czf backup_$(date +%Y%m%d).tar.gz chroma_db/ gxs_help_content/

# Deploy to Cloud Run
gcloud builds submit --tag gcr.io/vernac-479217/cx-buddy && gcloud run deploy cx-buddy --image gcr.io/vernac-479217/cx-buddy --quiet
```

---

**Built with ❤️ for GXS Bank customers**
