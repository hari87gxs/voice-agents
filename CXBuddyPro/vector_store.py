"""
Vector Store Manager for CXBuddy Knowledge Base
Uses ChromaDB with Azure OpenAI embeddings for semantic search
"""

import os
import json
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class GXSVectorStore:
    """
    Manages ChromaDB vector store for GXS Help Center content.
    Uses Azure OpenAI text-embedding-ada-002 for embeddings.
    """
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "gxs_help_center",
        azure_endpoint: Optional[str] = None,
        azure_api_key: Optional[str] = None,
        embedding_deployment: str = "text-embedding-ada-002"
    ):
        """
        Initialize vector store with Azure OpenAI embeddings.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the ChromaDB collection
            azure_endpoint: Azure OpenAI endpoint URL
            azure_api_key: Azure OpenAI API key
            embedding_deployment: Azure OpenAI embedding model deployment name
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_deployment = embedding_deployment
        
        # Initialize Azure OpenAI client for embeddings
        self.azure_client = AzureOpenAI(
            api_key=azure_api_key or os.getenv("AZURE_EMBEDDING_API_KEY"),
            api_version="2023-05-15",
            azure_endpoint=azure_endpoint or os.getenv("AZURE_EMBEDDING_ENDPOINT")
        )
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(name=collection_name)
            logger.info(f"✓ Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"description": "GXS Bank Help Center knowledge base"}
            )
            logger.info(f"✓ Created new collection: {collection_name}")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector from Azure OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.azure_client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"❌ Embedding error: {e}")
            raise
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks for better retrieval.
        
        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Number of overlapping characters between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for period, question mark, or exclamation within last 100 chars
                last_100 = text[max(start, end-100):end]
                for delimiter in ['. ', '? ', '! ', '\n\n']:
                    last_delim = last_100.rfind(delimiter)
                    if last_delim != -1:
                        end = max(start, end-100) + last_delim + len(delimiter)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def index_knowledge_base(self, knowledge_file: str, force_reindex: bool = False) -> int:
        """
        Index GXS help content into vector store.
        
        Args:
            knowledge_file: Path to consolidated knowledge file
            force_reindex: If True, clear existing collection and reindex
            
        Returns:
            Number of chunks indexed
        """
        # Check if already indexed
        existing_count = self.collection.count()
        if existing_count > 0 and not force_reindex:
            logger.info(f"✓ Collection already has {existing_count} documents. Use force_reindex=True to rebuild.")
            return existing_count
        
        if force_reindex and existing_count > 0:
            logger.info(f"🔄 Clearing existing {existing_count} documents...")
            self.chroma_client.delete_collection(name=self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "GXS Bank Help Center knowledge base"}
            )
        
        # Load knowledge base
        logger.info(f"📖 Loading knowledge from: {knowledge_file}")
        with open(knowledge_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into sections first (by page breaks)
        sections = content.split('=' * 100)
        logger.info(f"📄 Found {len(sections)} sections in knowledge base")
        
        # Process each section
        all_chunks = []
        all_metadatas = []
        all_ids = []
        
        chunk_id = 0
        for section_idx, section in enumerate(sections):
            section = section.strip()
            if len(section) < 50:  # Skip very short sections
                continue
            
            # Extract metadata from section
            lines = section.split('\n')
            source = ""
            title = ""
            
            for line in lines[:5]:  # Check first 5 lines for metadata
                if line.startswith('SOURCE:'):
                    source = line.replace('SOURCE:', '').strip()
                elif line.startswith('TITLE:'):
                    title = line.replace('TITLE:', '').strip()
            
            # Remove metadata lines from content
            content_lines = [l for l in lines if not l.startswith('SOURCE:') and not l.startswith('TITLE:')]
            content_text = '\n'.join(content_lines).strip()
            
            # Chunk the section
            chunks = self.chunk_text(content_text, chunk_size=500, overlap=100)
            
            for chunk_idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    "source": source,
                    "title": title,
                    "section_id": section_idx,
                    "chunk_id": chunk_idx,
                    "total_chunks": len(chunks)
                })
                all_ids.append(f"chunk_{chunk_id}")
                chunk_id += 1
        
        logger.info(f"🔢 Created {len(all_chunks)} chunks from {len(sections)} sections")
        
        # Batch embed and add to ChromaDB
        batch_size = 50
        total_batches = (len(all_chunks) + batch_size - 1) // batch_size
        
        for i in range(0, len(all_chunks), batch_size):
            batch_chunks = all_chunks[i:i+batch_size]
            batch_metadatas = all_metadatas[i:i+batch_size]
            batch_ids = all_ids[i:i+batch_size]
            
            # Get embeddings for batch
            logger.info(f"🔄 Embedding batch {i//batch_size + 1}/{total_batches} ({len(batch_chunks)} chunks)...")
            batch_embeddings = [self.get_embedding(chunk) for chunk in batch_chunks]
            
            # Add to ChromaDB
            self.collection.add(
                documents=batch_chunks,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
        
        final_count = self.collection.count()
        logger.info(f"✅ Indexed {final_count} chunks into vector store")
        
        return final_count
    
    def search(self, query: str, n_results: int = 3) -> str:
        """
        Semantic search in knowledge base.
        
        Args:
            query: User's question
            n_results: Number of results to return
            
        Returns:
            Formatted string with top matching content
        """
        try:
            # Get query embedding
            query_embedding = self.get_embedding(query)
            
            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 2  # Get more to deduplicate
            )
            
            if not results['documents'] or not results['documents'][0]:
                logger.warning(f"⚠ No results found for query: {query}")
                return "No information found for this query. Please check help.gxs.com.sg directly."
            
            # Deduplicate and format results
            unique_results = []
            seen_content = set()
            
            for i, doc in enumerate(results['documents'][0]):
                # Skip duplicates
                if doc in seen_content:
                    continue
                seen_content.add(doc)
                
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i] if 'distances' in results else None
                
                # Format result with metadata
                result_text = doc
                if metadata.get('title'):
                    result_text = f"[{metadata['title']}]\n{doc}"
                
                unique_results.append(result_text)
                
                if len(unique_results) >= n_results:
                    break
            
            formatted_results = '\n\n---\n\n'.join(unique_results)
            logger.info(f"✓ Found {len(unique_results)} unique results for query: {query}")
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return "Sorry, I encountered an error searching the knowledge base. Please try again."
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_documents": count,
            "persist_directory": self.persist_directory,
            "embedding_model": self.embedding_deployment
        }


# Global instance (initialized in server.py)
vector_store: Optional[GXSVectorStore] = None


def initialize_vector_store(
    knowledge_file: str,
    force_reindex: bool = False,
    **kwargs
) -> GXSVectorStore:
    """
    Initialize and index the vector store.
    
    Args:
        knowledge_file: Path to consolidated knowledge file
        force_reindex: If True, rebuild the index
        **kwargs: Additional arguments for GXSVectorStore
        
    Returns:
        Initialized GXSVectorStore instance
    """
    global vector_store
    
    logger.info("🚀 Initializing GXS Vector Store...")
    vector_store = GXSVectorStore(**kwargs)
    
    # Index knowledge base
    if os.path.exists(knowledge_file):
        vector_store.index_knowledge_base(knowledge_file, force_reindex=force_reindex)
    else:
        logger.warning(f"⚠ Knowledge file not found: {knowledge_file}")
    
    # Print stats
    stats = vector_store.get_stats()
    logger.info(f"📊 Vector Store Stats: {json.dumps(stats, indent=2)}")
    
    return vector_store
