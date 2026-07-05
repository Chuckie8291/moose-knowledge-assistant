# Moose Knowledge Assistant

**Ask anything about the Loyal Order of Moose and get answers backed by official governing documents — with exact citations.**

---

## Quick Start (Local Demo)

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt
pip install sentence-transformers faiss-cpu

# 2. Download the General Laws PDF
python scripts/download_gl.py

# 3. Build the search index + start the API
python scripts/demo.py

# 4. Open http://localhost:8000/docs to try the API
```

### CLI Query

```bash
# Set your OpenAI key first
export OPENAI_API_KEY=sk-...

# Build index + run a query
python scripts/demo.py --query "Can a governor fire a bartender?"
```

---

## Architecture

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14+ (React, TypeScript, Tailwind) |
| **Backend API** | FastAPI (Python 3.11+) |
| **Vector Search** | FAISS + sentence-transformers |
| **LLM** | OpenAI GPT-4o / GPT-4o-mini |
| **Full Stack** | PostgreSQL + pgvector + Elasticsearch + Redis (Docker) |

See `.hermes/plans/` for the complete architecture design (5 documents, 437 KB).

---

## Project Structure

```
moose-knowledge-assistant/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routes (query, documents, admin)
│   │   ├── core/
│   │   │   ├── ingestion/   # Document loading, OCR, chunking, embedding
│   │   │   ├── retrieval/   # Vector search, hybrid retrieval
│   │   │   └── generation/  # LLM prompt engineering, citation parsing
│   │   └── models/          # SQLAlchemy ORM models
│   └── tests/
├── frontend/                # Next.js app (being built by sub-agent)
├── scripts/                 # Demo runner, downloader, pipeline tests
├── data/                    # PDFs, FAISS index, pipeline outputs
└── docker/                  # Docker Compose for full stack
```
