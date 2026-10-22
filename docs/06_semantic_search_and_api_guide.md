# 06 — Semantic Search, Chunks Inspection & Frontend Integration

## 1. Overview
This guide provides the complete API specification and frontend integration patterns for the platform's AI retrieval endpoints:
1. **`POST /documents/search`**: Semantic Vector Similarity Search.
2. **`GET /documents/{document_id}/chunks`**: Document Chunk Inspector & Citations.
3. **`POST /documents/{document_id}/process`**: Manual / Re-trigger Processing.

---

## 2. API Specification

### Endpoint 1: Semantic Vector Search
Executes natural-language semantic similarity search across all documents or scoped to a specific collection/document.

* **Route:** `POST /documents/search`
* **Authentication:** Bearer JWT Access Token
* **Content-Type:** `application/json`

#### Request Body (`ChunkSearchRequest`):
```json
{
  "query": "How much revenue did North America generate in Q4?",
  "collection_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "document_id": null,
  "limit": 5
}
```

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `query` | `string` | **Yes** | Natural language search text (min length: 1). |
| `collection_id` | `string` | Optional | Scope search within a specific collection/knowledge base. |
| `document_id` | `string` | Optional | Scope search within a single document. |
| `limit` | `integer` | Optional | Maximum number of matching chunks to return (default: 5, max: 50). |

#### Response (`HTTP 200 OK`):
```json
{
  "success": true,
  "message": "Found 3 matching chunk(s)",
  "data": [
    {
      "id": "c1f2e3d4-0000-1111-2222-333344445555",
      "document_id": "0fa373fd-7280-4e74-8de5-6a83d006d1e7",
      "collection_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "content": "Q4 Financial Summary\nRevenue by Region\nNorth America, Q4 Revenue = $45M. YoY Growth = +32%",
      "metadata": {
        "headings": ["Q4 Financial Summary", "Revenue by Region"],
        "origin": { "filename": "q4_financial_summary.md" },
        "char_count": 225,
        "estimated_tokens": 56
      },
      "similarity": 0.7989
    }
  ]
}
```

---

### Endpoint 2: Get Document Chunks (Inspector & Citations)
Retrieves all parsed text chunks, Markdown tables, token counts, and layout metadata for a specific document.

* **Route:** `GET /documents/{document_id}/chunks`
* **Authentication:** Bearer JWT Access Token
* **Query Parameters:**
  * `limit` (int, default: 100, max: 500)
  * `offset` (int, default: 0)

#### Response (`HTTP 200 OK`):
```json
{
  "success": true,
  "message": "Document chunks retrieved successfully",
  "data": {
    "document_id": "0fa373fd-7280-4e74-8de5-6a83d006d1e7",
    "total_chunks": 3,
    "chunks": [
      {
        "id": "chunk_uuid_0",
        "document_id": "0fa373fd-7280-4e74-8de5-6a83d006d1e7",
        "collection_id": null,
        "chunk_index": 0,
        "content": "Q4 Financial Summary\nExecutive Overview\nThe company achieved record revenue in the fourth quarter...",
        "token_count": 46,
        "char_count": 187,
        "metadata": {
          "headings": ["Q4 Financial Summary", "Executive Overview"]
        },
        "created_at": "2026-10-23T00:15:00Z"
      }
    ]
  }
}
```

---

### Endpoint 3: Trigger / Re-process Document
Dispatches document processing into the Celery distributed queue or runs synchronously.

* **Route:** `POST /documents/{document_id}/process`
* **Authentication:** Bearer JWT Access Token
* **Query Parameters:**
  * `run_in_background` (bool, default: `true`). When `true`, delegates to Celery (`202 Accepted`). When `false`, blocks until processing finishes.

#### Response (`HTTP 202 Accepted`):
```json
{
  "success": true,
  "message": "Document processing queued in Celery worker queue (task_id: e6f43e12-8822-4a57-a12b-348123abc456)",
  "data": {
    "document_id": "0fa373fd-7280-4e74-8de5-6a83d006d1e7",
    "status": "queued",
    "total_chunks": 0,
    "error_message": null,
    "doc_metadata": {
      "celery_task_id": "e6f43e12-8822-4a57-a12b-348123abc456"
    },
    "updated_at": "2026-10-23T00:15:00Z"
  }
}
```

---

## 3. Frontend UI Implementation Blueprints

### Blueprint 1: Spotlight Semantic Search Bar (Notion / Perplexity Style)

```typescript
// Example: React/TypeScript search handler
async function handleSemanticSearch(query: string, collectionId?: string) {
  const response = await api.post("/documents/search", {
    query: query,
    collection_id: collectionId || null,
    limit: 5,
  });

  // Returns matching chunks ranked by cosine similarity
  return response.data.data;
}
```

```
┌────────────────────────────────────────────────────────────────────────┐
│  🔍 Search: "What are the rules for termination penalties?"            │
├────────────────────────────────────────────────────────────────────────┤
│  MATCHES FOUND (Top 2 relevant chunks):                                │
│                                                                        │
│  📄 Supplier_Master_Agreement.pdf  •  [ 88% Semantic Match ]           │
│  "...in the event of early termination under Section 4.2, contractor   │
│   shall forfeit 15% of the retained milestone deposit..."              │
│                                                                        │
│  📄 Service_Level_Agreement.docx   •  [ 73% Semantic Match ]           │
│  "...penalties shall not exceed 10% of monthly billing..."             │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Blueprint 2: Document Inspector & Source Citation View

When an AI Assistant answers:
> *"The Asian market grew by 40% in Q4."* **`[Source 1]`**

The user clicks **`[Source 1]`**. The frontend opens a drawer or modal, calls `GET /documents/{id}/chunks`, and highlights the exact Markdown chunk:

```
┌────────────────────────────────────────────────────────────┐
│  Source Verification: Chunk #2                             │
├────────────────────────────────────────────────────────────┤
│  Document: q4_financial_summary.md                         │
│  Heading:  Revenue by Region                               │
│                                                            │
│  ┌──────────────┬──────────────┬─────────────┐             │
│  │ Region       │ Q4 Revenue   │ YoY Growth  │             │
│  ├──────────────┼──────────────┼─────────────┤             │
│  │ Asia Pacific │ $19M         │ +40%        │ <── Highlight
│  └──────────────┴──────────────┴─────────────┘             │
└────────────────────────────────────────────────────────────┘
```

---

### Blueprint 3: Asynchronous Status Polling

Because uploads return `202 Accepted` immediately, the frontend can poll `GET /documents/{document_id}` or `GET /documents?collection_id={id}` every 2 seconds until the status changes from `processing` to `completed`:

```typescript
function pollDocumentStatus(documentId: string, onComplete: () => void) {
  const interval = setInterval(async () => {
    const res = await api.get(`/documents/${documentId}`);
    const status = res.data.data.status;

    if (status === "completed") {
      clearInterval(interval);
      onComplete(); // Remove spinner, display green checkmark & chunk count
    } else if (status === "failed") {
      clearInterval(interval);
      showErrorToast(res.data.data.error_message);
    }
  }, 2000);
}
```

---

## 4. Postman Collection Integration

All endpoints are organized in the Postman collection ([`ai-document-intelligence-platform.json`](file:///D:/Code/Projects/ai-document-intelligence-platform/ai-document-intelligence-platform.json)):

```
AI Document Intelligence Platform API
├── System & Health
├── Authentication
├── Collections
├── Documents
└── AI Processing & Vector Search
    ├── 1. Trigger / Re-process Document
    ├── 2. Get Document Chunks
    └── 3. Semantic Vector Search
```
* Automatic environment variable capture preserves `access_token`, `collection_id`, and `document_id` across requests for zero-configuration testing.

---

### Navigation
[← Previous: 05 — Vector Embeddings & pgvector](./05_embeddings_and_vector_store.md) | [Documentation Blueprint](./README.md)
