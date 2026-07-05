r"""
build_index.py — Build a FAISS vector index from the Moose General Laws PDF.

Pipeline:
  1. Load the PDF (data/Aug-2025-General-Laws.pdf)
  2. Classify + extract structure
  3. Chunk into retrieval-optimized pieces
  4. Embed with sentence-transformers (all-MiniLM-L6-v2, local, free)
  5. Build FAISS index
  6. Save to data/faiss_index/

No Docker, PostgreSQL, Elasticsearch, or OpenAI API key required.

Usage:
    cd "C:\Users\Chuck\Desktop\Ask Anything moose"
    python scripts/build_index.py

    # Or with custom options:
    python scripts/build_index.py --model all-MiniLM-L6-v2 --output data/faiss_index/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────

# Determine project root (where data/ and backend/ live)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data"

# Add backend to Python path
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))  # So relative config/env paths resolve


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build FAISS vector index from Moose General Laws PDF"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=str(DATA_DIR / "Aug-2025-General-Laws.pdf"),
        help="Path to the PDF file (default: data/Aug-2025-General-Laws.pdf)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DATA_DIR / "faiss_index"),
        help="Output directory for FAISS index (default: data/faiss_index/)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--skip-toc",
        type=int,
        default=6,
        help="Skip first N pages (Table of Contents). Default: 6",
    )
    parser.add_argument(
        "--min-chunk-tokens",
        type=int,
        default=10,
        help="Minimum tokens per chunk (filter tiny chunks). Default: 10",
    )
    parser.add_argument(
        "--doc-type",
        type=str,
        default="general_laws",
        help="Document type override (default: general_laws)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="General Laws of the Moose Fraternity",
        help="Document title",
    )
    parser.add_argument(
        "--effective-date",
        type=str,
        default="2025-08-01",
        help="Effective date of the document (default: 2025-08-01)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    pdf_path = Path(args.pdf)
    output_dir = Path(args.output)

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        print(f"   Download it first: scripts/run_pipeline_e2e.py")
        sys.exit(1)

    print("=" * 70)
    print("  MOOSE KNOWLEDGE ASSISTANT — FAISS INDEX BUILDER")
    print("=" * 70)
    print(f"  PDF:       {pdf_path}")
    print(f"  Output:    {output_dir}")
    print(f"  Model:     {args.model}")
    print(f"  Doc type:  {args.doc_type}")
    print()

    # ═══════════════════════════════════════════════════════════
    # STAGE 1: LOAD DOCUMENT
    # ═══════════════════════════════════════════════════════════
    print("─" * 70)
    print("STAGE 1: Loading document...")
    t0 = time.time()

    from app.core.ingestion.document_loader import DocumentLoader
    loader = DocumentLoader()
    loaded = loader.load(str(pdf_path))

    print(f"  Pages:      {loaded.total_pages}")
    print(f"  Characters: {loaded.total_chars:,}")
    print(f"  Digital:    {loaded.is_digital}")
    print(f"  Hash:       {loaded.content_hash[:16]}...")
    print(f"  Time:       {time.time() - t0:.1f}s")

    # ═══════════════════════════════════════════════════════════
    # STAGE 2: CLASSIFY
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 2: Classifying document...")
    t0 = time.time()

    from app.core.ingestion.classifier import DocumentClassifier, DOC_TYPES
    classifier = DocumentClassifier()

    # Use admin override if specified
    type_info = DOC_TYPES.get(args.doc_type, DOC_TYPES["other"])
    from app.core.ingestion.classifier import ClassificationResult
    classification = ClassificationResult(
        doc_type=args.doc_type,
        tier=type_info["tier"],
        category=type_info["category"],
        citation_format=type_info["citation_format"],
        label=type_info["label"],
        confidence=1.0,
        needs_admin_review=False,
        detected_jurisdiction="international",
    )

    print(f"  Type:       {classification.label}")
    print(f"  Tier:       {classification.tier}")
    print(f"  Category:   {classification.category}")

    # ═══════════════════════════════════════════════════════════
    # STAGE 3: EXTRACT STRUCTURE
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 3: Extracting document structure...")
    t0 = time.time()

    from app.core.ingestion.structure_extractor import get_structure_extractor

    # Skip TOC pages
    body_pages = [p for p in loaded.pages if p.page_number >= args.skip_toc]
    full_text = "\n\n".join(p.text for p in body_pages)

    # Build page map from body pages
    page_map = {}
    char_pos = 0
    for page in body_pages:
        page_map[char_pos] = page.page_number
        char_pos += len(page.text) + 2

    extractor = get_structure_extractor(classification.doc_type)
    tree = extractor.extract(full_text, page_map)

    all_sections = tree.all_sections()
    leaf_sections = tree.leaf_sections()
    print(f"  Total sections:    {len(all_sections)}")
    print(f"  Leaf sections:     {len(leaf_sections)}")
    print(f"  Time:              {time.time() - t0:.1f}s")

    # Print section tree overview
    print("\n  Section tree (top levels):")
    for section in all_sections[:10]:
        indent = "  " * (section.level - 1)
        print(f"    {indent}§{section.section_number} — {section.title[:70]}")
    if len(all_sections) > 10:
        print(f"    ... ({len(all_sections) - 10} more)")

    # ═══════════════════════════════════════════════════════════
    # STAGE 4: CHUNK
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 4: Chunking document...")
    t0 = time.time()

    from app.core.ingestion.chunker import get_chunker

    chunker = get_chunker(classification.doc_type)
    raw_chunks = chunker.chunk(
        tree=tree,
        doc_short_title=args.title,
        doc_tier=classification.tier,
        effective_date=args.effective_date,
    )

    # Filter tiny chunks (page numbers, artifacts)
    chunks = [c for c in raw_chunks if c.token_count >= args.min_chunk_tokens]
    filtered = len(raw_chunks) - len(chunks)
    if filtered:
        print(f"  Filtered {filtered} tiny chunks (< {args.min_chunk_tokens} tokens)")

    total_tokens = sum(c.token_count for c in chunks)
    avg_tokens = total_tokens / max(len(chunks), 1)
    print(f"  Total chunks:  {len(chunks)}")
    print(f"  Total tokens:  {total_tokens:,}")
    print(f"  Avg tokens:    {avg_tokens:.0f}")
    print(f"  Time:          {time.time() - t0:.1f}s")

    # Attach classification metadata to each chunk
    for chunk in chunks:
        chunk.metadata["doc_type"] = classification.doc_type
        chunk.metadata["doc_category"] = classification.category
        chunk.metadata["doc_label"] = classification.label

    # ═══════════════════════════════════════════════════════════
    # STAGE 5: EMBED
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 5: Generating embeddings...")
    print(f"  Model: {args.model} (sentence-transformers, local)")
    print(f"  Chunks to embed: {len(chunks)}")
    t0 = time.time()

    from app.core.retrieval.vector_store import LocalEmbedder

    embedder = LocalEmbedder(model_name=args.model)
    chunks = embedder.embed_chunks(chunks, show_progress=True)

    print(f"  Dimension:  {embedder.dimension}")
    print(f"  Time:       {time.time() - t0:.1f}s")

    # ═══════════════════════════════════════════════════════════
    # STAGE 6: BUILD FAISS INDEX
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 6: Building FAISS index...")
    t0 = time.time()

    from app.core.retrieval.vector_store import FAISSVectorStore

    vector_store = FAISSVectorStore(dimension=embedder.dimension)
    indexed_ids = vector_store.add_chunks(chunks)

    print(f"  Vectors indexed: {len(indexed_ids)}")
    print(f"  Index size:      {vector_store.size}")
    print(f"  Time:            {time.time() - t0:.1f}s")

    # ═══════════════════════════════════════════════════════════
    # STAGE 7: SAVE TO DISK
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 7: Persisting index to disk...")
    t0 = time.time()

    vector_store.save(output_dir)

    print(f"  Output:  {output_dir.absolute()}")
    print(f"  Files:")
    for f in sorted(output_dir.glob("*")):
        size_kb = f.stat().st_size / 1024
        print(f"    {f.name} ({size_kb:.1f} KB)")
    print(f"  Time:    {time.time() - t0:.1f}s")

    # ═══════════════════════════════════════════════════════════
    # STAGE 8: VERIFY (quick sanity check)
    # ═══════════════════════════════════════════════════════════
    print("\n─" * 70)
    print("STAGE 8: Verifying index (sanity check)...")

    # Load it back
    loaded_store = FAISSVectorStore.load(output_dir)
    print(f"  Loaded store: {loaded_store.size} vectors (dim={loaded_store.dimension})")

    # Run a test query
    test_query = "What are the duties of the Governor?"
    print(f"\n  Test query: \"{test_query}\"")

    query_emb = embedder.embed_query(test_query)
    results = loaded_store.search(query_emb, top_k=3)

    if results:
        print(f"\n  Top {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"    {i}. [{r.score:.4f}] §{r.section_number} — {r.section_title}")
            preview = r.content_text[:120].replace('\n', ' ')
            print(f"       {preview}...")
    else:
        print("  ❌ No results returned — index may be empty")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  BUILD COMPLETE ✅")
    print("=" * 70)
    print(f"  Chunks indexed:  {len(chunks)}")
    print(f"  Embedding model: {args.model} ({embedder.dimension}d)")
    print(f"  Index location:  {output_dir.absolute()}")
    print()
    print("  Next steps:")
    print(f"    1. Use the index in your app:")
    print(f"       from app.core.retrieval.vector_store import FAISSVectorStore")
    print(f'       store = FAISSVectorStore.load("{output_dir}")')
    print(f"    2. Search with HybridRetriever:")
    print(f"       from app.core.retrieval.hybrid_retriever import HybridRetriever")
    print(f"       retriever = HybridRetriever()")
    print(f'       results = retriever.retrieve("your question here")')


if __name__ == "__main__":
    main()
