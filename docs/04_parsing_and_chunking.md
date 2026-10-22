# 04 — Layout-Aware Document Parsing & Hybrid Chunking (LangChain + Docling)

## 1. Why Traditional Document Parsers Fail on Enterprise Files

Most standard RAG tutorials use simple text extractors (like `PyPDF2` or naive string splitting). In real enterprise documents, this causes severe degradation:

### The Problem with Naive Parsers:
1. **Broken Multi-Column Tables:**
   Standard text extractors read text left-to-right across columns. A financial balance sheet becomes a garbled stream of numbers where columns, rows, and headers are intermingled and unreadable.
2. **Loss of Heading Context:**
   If a text splitter blindly chops text at 1,000 characters, a crucial paragraph under `"Section 4.2: Termination Penalties"` might be detached from its heading. When an LLM retrieves that chunk, it has no idea what clause it belongs to.
3. **Destroyed Reading Order:**
   Multi-column PDFs (like scientific papers or corporate annual reports) are read across columns rather than down the column, scrambling the narrative.

---

## 2. IBM Docling Architecture

To solve these limitations, the platform uses **IBM Docling** via **LangChain** (`langchain-docling`):

```
┌────────────────────────────────────────────────────────┐
│                   Input Document                       │
│        (PDF, DOCX, Markdown, Text, or Image)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 IBM Docling Engine                     │
│                                                        │
│  • Visual Layout Analysis (LayoutLM / Vision AI)       │
│  • Table Structure Recognition (TS-Model)              │
│  • OCR (for scanned pages / embedded images)           │
│  • Heading Hierarchy & Reading Order Detection         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Extracted Document Model                   │
│                                                        │
│  • Tables preserved as intact Markdown tables          │
│  • Headings tagged with parent-child relationships     │
│  • Code blocks and lists isolated                      │
└────────────────────────────────────────────────────────┘
```

### Table Extraction Comparison:

#### ❌ What a Naive Extractor Produces:
```
Year Revenue Margin 2024 $10M 15% 2025 $14M 19%
```
*(Vector search cannot reliably answer: "What was the 2025 margin?" because relationships are lost).*

#### ✅ What Docling Produces:
```markdown
| Year | Revenue | Operating Margin |
| :--- | :--- | :--- |
| 2024 | $10M | 15% |
| 2025 | $14M | 19% |
```
*(Vector embeddings capture the precise cell-to-column context, allowing high-precision semantic search).*

---

## 3. LangChain Integration with Thread Isolation

Document layout analysis and OCR are CPU-heavy operations. Running them directly inside Python's asynchronous event loop would block all other concurrent requests.

In [`DoclingDocumentParser`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/modules/processing/parsers/docling_parser.py), we isolate Docling inside a background worker thread using `asyncio.to_thread`:

```python
class DoclingDocumentParser(BaseDocumentParser):
    def __init__(self, export_type: ExportType = ExportType.DOC_CHUNKS):
        self.export_type = export_type

    def _load_sync(self, file_path: str) -> list[LCDocument]:
        # Synchronous Docling execution
        loader = DoclingLoader(file_path=file_path, export_type=self.export_type)
        return loader.load()

    async def parse(self, file_path: str | Path, **kwargs) -> list[LCDocument]:
        # Executed in a dedicated thread pool to keep the event loop free
        try:
            docs = await asyncio.to_thread(self._load_sync, str(file_path))
        except Exception as exc:
            # Automatic fallback: if DOC_CHUNKS fails, attempt full MARKDOWN export
            if self.export_type != ExportType.MARKDOWN:
                fallback_loader = DoclingLoader(file_path=str(file_path), export_type=ExportType.MARKDOWN)
                docs = await asyncio.to_thread(fallback_loader.load)
            else:
                raise exc
        return docs
```

---

## 4. The Hybrid Chunking Strategy

Once Docling parses the document, the chunks are processed by [`HybridDocumentChunker`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/modules/processing/chunkers/hybrid_chunker.py).

### How Hybrid Chunking Works:
1. **Layout-Aware First:** Docling groups content by natural section boundaries and keeps entire tables intact in individual chunks.
2. **Size Enforcement:** If a section or table is abnormally large (e.g. exceeds `CHUNK_SIZE = 1000` characters), the hybrid chunker uses LangChain's `RecursiveCharacterTextSplitter` with intelligent separators:
   ```python
   separators = ["\n## ", "\n### ", "\n\n", "\n", " ", ""]
   ```
   This splits paragraphs cleanly without slicing words in half or severing markdown table pipes.
3. **Sequential Chunk Indexing:** Every chunk is assigned a sequential `chunk_index` (`0, 1, 2...`) so that downstream RAG systems can reconstruct the surrounding reading context.
4. **Token Estimation:** Calculates character length and provides a token estimate (`len(content) // 4`) for monitoring LLM context limits.
5. **Metadata Enrichment:** Retains Docling's rich structural metadata:
   ```json
   {
     "headings": ["Annual Report", "Revenue by Region"],
     "chunk_index": 1,
     "char_count": 225,
     "estimated_tokens": 56,
     "origin": { "filename": "q4_financial_summary.md" }
   }
   ```

---

## 5. Supported Document Formats & Underlying Engines

| Format | File Extensions | Parsing Engine Used |
| :--- | :--- | :--- |
| **PDF Documents** | `.pdf` | Docling LayoutLM + TS-Model (Table Structure) + OCR |
| **Word Documents** | `.docx`, `.doc` | Docling + `python-docx` XML layout parser |
| **Markdown** | `.md` | Docling + `marko` AST tree parser |
| **Plain Text & CSV** | `.txt`, `.csv` | Docling structure & delimiter parser |
| **Image Files** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff`, `.bmp` | Docling Optical Character Recognition (OCR) |

---

### Navigation
[← Previous: 03 — Celery & Redis Pipeline](./03_asynchronous_celery_pipeline.md) | [Documentation Blueprint](./README.md) | [Next: 05 — Vector Embeddings & pgvector →](./05_embeddings_and_vector_store.md)
