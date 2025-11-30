"""
Test script for vector store functionality
Creates a small test knowledge base and verifies embedding + search works
"""

import os
from dotenv import load_dotenv
from vector_store import GXSVectorStore

# Load environment
load_dotenv()

# Create test data
test_content = """
================================================================================
SOURCE: https://help.gxs.com.sg/test1
TITLE: How to freeze your GXS FlexiCard

You can temporarily stop usage of your GXS FlexiCard by freezing it. If you would like to use your card again, simply unfreeze it.

Here's how you can freeze/unfreeze your GXS FlexiCard:
1. Log in to the GXS Bank app.
2. On the GXS FlexiCard homescreen, tap on 'Freeze' or 'Unfreeze'.
3. Confirm the Freeze or Unfreeze request.

================================================================================
SOURCE: https://help.gxs.com.sg/test2
TITLE: GXS Savings Account Interest Rates

Are the interest rates different for my Main Account and Saving Pockets?

Yes, the interest rates are different:
- Main Account: 2.18% p.a. on first S$100,000
- Saving Pockets: Up to 2.48% p.a. on first S$100,000

Interest is calculated daily and credited monthly.

================================================================================
SOURCE: https://help.gxs.com.sg/test3
TITLE: GXS FlexiCard Fees

GXS FlexiCard is an interest-free, fee-based credit card.

Fees:
- Monthly subscription: S$4.99
- Late payment fee: S$50
- Foreign transaction fee: 3.5%

You can request a fee waiver for certain fees.
"""

# Write test data
os.makedirs('test_knowledge', exist_ok=True)
with open('test_knowledge/test_consolidated.txt', 'w') as f:
    f.write(test_content)

print("🧪 Testing Vector Store\n")

# Initialize vector store
print("1️⃣ Initializing vector store...")
store = GXSVectorStore(
    persist_directory="./test_chroma_db",
    collection_name="gxs_test",
    azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
    azure_api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
    embedding_deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
)

# Index test data
print("\n2️⃣ Indexing test knowledge base...")
num_chunks = store.index_knowledge_base('test_knowledge/test_consolidated.txt', force_reindex=True)
print(f"✅ Indexed {num_chunks} chunks")

# Test searches
print("\n3️⃣ Testing semantic search...\n")

test_queries = [
    "How do I freeze my FlexiCard?",
    "What are the interest rates for savings?",
    "What fees does FlexiCard have?"
]

for query in test_queries:
    print(f"📝 Query: {query}")
    result = store.search(query, n_results=1)
    print(f"📊 Result:\n{result[:200]}...\n")

# Show stats
print("\n4️⃣ Vector Store Stats:")
stats = store.get_stats()
for key, value in stats.items():
    print(f"   {key}: {value}")

print("\n✅ Vector store test completed successfully!")
print("\n💡 If all searches returned relevant results, the vector store is working correctly.")
