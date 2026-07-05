"""
Unified Demo Runner — One command to start the Moose Knowledge Assistant.

Usage:
    python scripts/demo.py              # Build index + start API server
    python scripts/demo.py --build-only # Just build the FAISS index
    python scripts/demo.py --serve-only # Just start the API (index must exist)
    python scripts/demo.py --query "Can a governor fire a bartender?"  # CLI query

Requirements:
    pip install fastapi uvicorn openai sentence-transformers faiss-cpu
"""

import argparse, sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT_ROOT / "backend"
DATA = PROJECT_ROOT / "data"
sys.path.insert(0, str(BACKEND))

# ── CLI ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Moose Knowledge Assistant Demo")
    parser.add_argument("--build-only", action="store_true", help="Only build the FAISS index")
    parser.add_argument("--serve-only", action="store_true", help="Only start the API server")
    parser.add_argument("--query", type=str, help="Run a single query via CLI")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload (dev)")
    args = parser.parse_args()

    if args.query:
        return run_query(args.query)

    if not args.serve_only:
        build_index()

    if not args.build_only:
        start_server(args.port, args.reload)


# ── Build FAISS Index ──────────────────────────────────────

def build_index():
    """Build FAISS index using scripts/build_index.py (LocalEmbedder, free)."""
    import subprocess
    build_script = PROJECT_ROOT / "scripts" / "build_index.py"
    if not build_script.exists():
        print(f"  ❌  Build script not found: {build_script}")
        sys.exit(1)
    print("  Running build_index.py (sentence-transformers, local, free)...")
    result = subprocess.run([sys.executable, str(build_script)], cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("\n  ❌  Index build failed")
        sys.exit(1)


# ── Start API Server ───────────────────────────────────────

def start_server(port: int, reload: bool):
    """Start the FastAPI server."""
    print("=" * 60)
    print(f"  STARTING API SERVER on http://localhost:{port}")
    print("=" * 60)
    print(f"\n  📡  API:        http://localhost:{port}")
    print(f"  📖  Docs:       http://localhost:{port}/docs")
    print(f"  ❓  Ask:        POST http://localhost:{port}/api/v1/query")
    print(f"\n  Press Ctrl+C to stop\n")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info",
    )


# ── CLI Query ──────────────────────────────────────────────

def run_query(query: str):
    """Run a single query via the CLI."""
    print(f"\n  ❓  {query}\n")

    index_dir = DATA / "faiss_index"
    if not (index_dir / "faiss.index").exists():
        print("  No index found. Building first...")
        build_index()

    from app.core.retrieval.vector_store import FAISSVectorStore, LocalEmbedder

    store = FAISSVectorStore.load(index_dir)
    embedder = LocalEmbedder("all-MiniLM-L6-v2")
    query_emb = embedder.embed_query(query)
    results = store.search(query_emb, top_k=8)
    print(f"  Top results:\n")
    for i, r in enumerate(results[:5]):
        print(f"  [{i+1}] score={r.score:.3f} | §{r.section_number}")
        print(f"       {r.content_text[:150]}...\n")

    # If API key is set, generate answer
    api_key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if api_key and not api_key.startswith("sk-your-key"):
        print("  🤖  Generating AI answer...\n")
        from openai import OpenAI
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        client = OpenAI(api_key=api_key, base_url=base_url)
        model = os.environ.get("LLM_MODEL", "deepseek-chat")

        # Build context from results
        context_parts = []
        for r in results:
            if r.score < 0.3:
                break
            context_parts.append(f"{r.citation_header}\n{r.content_text}")
        context = "\n\n".join(context_parts)

        system = """You are the Moose Knowledge Assistant. Answer using ONLY the provided sources.
Every factual claim must include [Cite: document, §section — "exact quote"].
Format: CONCISE ANSWER, DETAILED EXPLANATION, CITATIONS, CONFIDENCE."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"SOURCES:\n{context}\n\nQUESTION: {query}"},
            ],
            temperature=0.1,
        )
        print(response.choices[0].message.content)
    else:
        print("  💡  Set OPENAI_API_KEY in .env to enable AI-generated answers.")
        print("  Above are the raw retrieved chunks you can read manually.")


if __name__ == "__main__":
    main()
