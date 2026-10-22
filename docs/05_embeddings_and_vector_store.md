# 05 — Vector Embeddings & Supabase pgvector Indexing

## 1. Overview & Architecture
This subsystem transforms text chunks into mathematical vectors (dense arrays of 384 floating-point numbers) and indexes them into **Supabase PostgreSQL** using the **`pgvector`** extension with **HNSW (Hierarchical Navigable Small World)** indexing.

```mermaid
flowchart LR
    Chunk[Text Chunk<br/>'North America revenue was $45M'] --> FastEmbed[FastEmbed ONNX Engine<br/>BAAI/bge-small-en-v1.5]
    FastEmbed --> Vector["Dense Vector [384 dims]<br/>[-0.033, 0.081, 0.002, ...]"]
    Vector --> PostgresTable[(document_chunks Table<br/>Column: embedding vector(384))]
    PostgresTable --> HNSWIndex[HNSW Vector Graph Index<br/>vector_cosine_ops]
```

---

## 2. Why FastEmbed (`bge-small-en-v1.5`) Over Alternatives?

When selecting an embedding provider for production document intelligence, three main options were evaluated:

| Factor | OpenAI (`text-embedding-3-small`) | Standard HuggingFace (`sentence-transformers`) | FastEmbed (`bge-small-en-v1.5`) [Chosen] |
| :--- | :--- | :--- | :--- |
| **API Cost** | ❌ Paid per token ($0.02 / 1M tokens) | ✅ $0 (Runs locally) | ✅ **$0 (Runs locally)** |
| **Dependencies** | ✅ Lightweight `openai` package | ❌ Requires **PyTorch (3GB to 4GB download)** | ✅ **Uses ONNX Runtime (~50MB)** |
| **RAM Usage** | Low (calls external API) | High (~1.5GB to 2GB idle RAM) | **Very Low (~120MB working RAM)** |
| **Network Latency** | ~200ms–500ms network roundtrip | 0ms (In-memory) | **0ms (In-memory, ~15ms per chunk)** |
| **Data Privacy** | ❌ Data sent over internet to third party | ✅ 100% On-Premise / Private | ✅ **100% On-Premise / Private** |
| **Benchmark (MTEB)** | High (62.3 score) | Moderate to High | **Top-tier (BGE ranks #1 in small models)** |

### Conclusion:
`FastEmbed` provides **enterprise-grade semantic search for $0 cost**, with zero PyTorch bloat and zero external API dependencies.

---

## 3. The Embedding Factory (`EmbeddingFactory`)

To adhere to clean architecture, embeddings are initialized via an abstract factory:

```python
class EmbeddingFactory:
    _cached_instance: Embeddings | None = None

    @classmethod
    def get_embeddings(cls, provider: str | None = None, model: str | None = None) -> Embeddings:
        # Singleton caching prevents reloading 67MB ONNX model weights on every request
        if provider is None and model is None and cls._cached_instance is not None:
            return cls._cached_instance

        chosen_provider = (provider or settings.EMBEDDING_PROVIDER).lower()
        chosen_model = model or settings.EMBEDDING_MODEL

        if chosen_provider == "fastembed":
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            instance = FastEmbedEmbeddings(model_name=chosen_model)
        elif chosen_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            instance = OpenAIEmbeddings(model=chosen_model)
        elif chosen_provider == "gemini":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            instance = GoogleGenerativeAIEmbeddings(model=chosen_model)
        else:
            raise ValueError(f"Unsupported provider: {chosen_provider}")

        if provider is None and model is None:
            cls._cached_instance = instance
        return instance
```

---

## 4. PostgreSQL Schema & Vector Indexing (`pgvector`)

### DDL Schema (`document_chunks` table):
Applied in migration `c3bb51f6204a`:

```sql
-- 1. Enable PostgreSQL vector extension in Supabase
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create chunks table
CREATE TABLE document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    collection_id VARCHAR REFERENCES collections(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER,
    char_count INTEGER NOT NULL,
    chunk_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Why HNSW Indexing Over IVFFlat?

PostgreSQL `pgvector` offers two primary index types: **IVFFlat** and **HNSW**.

```sql
CREATE INDEX idx_document_chunks_embedding 
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

| Feature | IVFFlat Index | HNSW Index (Chosen) |
| :--- | :--- | :--- |
| **Build Mechanism** | Inverted file index (clusters) | Multi-layer graph of vectors |
| **Requires Training?** | ❌ **Yes.** Needs existing data to cluster. Performance degrades as new data is inserted. | ✅ **No training required.** New vectors can be inserted dynamically at any time. |
| **Recall Accuracy** | ~85%–90% | **> 98% (Near ground-truth accuracy)** |
| **Query Speed** | Fast, but sensitive to `probes` setting | **Ultra-fast (< 2ms) sub-millisecond retrieval** |

### Cosine Distance vs Dot Product vs Euclidean:
We use **`vector_cosine_ops`** with the `<=>` cosine distance operator:
$$\text{Similarity} = 1 - (\text{embedding} \Leftrightarrow \text{query\_vector})$$
* **Why Cosine?** Text chunks vary in length. Cosine similarity measures the **angle** between vectors rather than their magnitude, ensuring a short paragraph and a long paragraph discussing the same topic have high similarity.

---

## 5. Multi-Tenant Scoped Queries

In multi-tenant SaaS applications, vector search must never leak data between different users or unrelated projects.

We enforce strict scoping using composite B-Tree indexes alongside HNSW:
```sql
CREATE INDEX ix_document_chunks_user_doc ON document_chunks (user_id, document_id);
CREATE INDEX ix_document_chunks_collection_id ON document_chunks (collection_id);
```

When a user executes a search:
```python
stmt = (
    select(DocumentChunk, (1 - DocumentChunk.embedding.cosine_distance(query_vector)).label("similarity"))
    .where(
        DocumentChunk.user_id == current_user.id,        # Strict tenant boundary
        DocumentChunk.collection_id == collection_id,    # Scoped knowledge base
    )
    .order_by(DocumentChunk.embedding.cosine_distance(query_vector).asc())
    .limit(limit)
)
```
* PostgreSQL utilizes the B-Tree index to filter down to the user's specific collection, and then uses the HNSW index to rank the vectors in sub-milliseconds.

---

### Navigation
[← Previous: 04 — Parsing & Chunking](./04_parsing_and_chunking.md) | [Documentation Blueprint](./README.md) | [Next: 06 — Semantic Search & Frontend Integration →](./06_semantic_search_and_api_guide.md)
