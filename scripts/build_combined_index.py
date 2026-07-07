"""
Build a combined FAISS index from all downloaded Moose PDFs using local embeddings.
Properly processes each PDF through the full ingestion pipeline, chunks all sections,
and embeds with sentence-transformers (free, local).
"""
import sys, os, json, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT_ROOT / "backend"
DATA = PROJECT_ROOT / "data"
sys.path.insert(0, str(BACKEND))

from app.core.ingestion.pipeline import IngestionPipeline
from app.core.retrieval.vector_store import FAISSVectorStore, LocalEmbedder


def main():
    pdf_dir = DATA / "pdfs"
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs\n")

    all_chunks = []
    success = 0
    
    for pdf_path in pdf_files:
        short_name = pdf_path.stem[:50]
        size_kb = pdf_path.stat().st_size / 1024
        print(f"📄 {short_name} ({size_kb:.0f} KB)...", end=" ", flush=True)
        
        try:
            # Run pipeline (skip the embed stage — we'll use LocalEmbedder)
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(pdf_path))
            
            if result.status == "error":
                doc_chunks = result.metadata.get("chunks", [])
                doc_chunks = [c for c in doc_chunks if hasattr(c, 'content_text') and c.content_text and len(c.content_text.strip()) > 20]
                if doc_chunks:
                    print(f"✓ {len(doc_chunks)} chunks (validation warnings ignored)")
                else:
                    print(f"✗")
                    continue
            else:
                chunks = result.metadata.get("chunks", [])
                doc_chunks = [c for c in chunks if hasattr(c, 'content_text') and c.content_text and len(c.content_text.strip()) > 20]
            
            # Enrich chunk metadata
            for c in doc_chunks:
                c.document_title = short_name
            
            all_chunks.extend(doc_chunks)
            success += 1
            print(f"✓ {len(doc_chunks)} chunks")
            
        except Exception as e:
            print(f"✗ {str(e)[:60]}")
    
    print(f"\n{'='*50}")
    print(f"Success: {success}/{len(pdf_files)} documents")
    print(f"Total chunks: {len(all_chunks)}")
    
    if not all_chunks:
        print("No chunks to index!")
        return
    
    # Show per-document breakdown
    docs = {}
    for c in all_chunks:
        title = getattr(c, 'document_title', '?')
        docs[title] = docs.get(title, 0) + 1
    print(f"\nPer document:")
    for title, count in sorted(docs.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {title}")
    
    # Generate embeddings locally
    print(f"\n🧠 Generating embeddings (sentence-transformers, local, free)...")
    embedder = LocalEmbedder("all-MiniLM-L6-v2")
    
    texts = [c.content_text for c in all_chunks]
    import numpy as np
    embeddings = embedder.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    print(f"   Generated {len(embeddings)} embeddings ({embedder.dimension}-dim)")
    
    # Build FAISS index
    print(f"\n📊 Building FAISS index...")
    store = FAISSVectorStore(dimension=embedder.dimension)
    
    # Create chunk data objects for add_embeddings
    chunk_datas = []
    for chunk in all_chunks:
        chunk_datas.append({
            "content_text": chunk.content_text,
            "section_number": getattr(chunk, 'section_number', '?'),
            "section_title": getattr(chunk, 'section_title', ''),
            "citation_header": getattr(chunk, 'citation_header', ''),
            "document_title": getattr(chunk, 'document_title', '?'),
            "page_start": getattr(chunk, 'page_start', 0),
            "page_end": getattr(chunk, 'page_end', 0),
        })
    
    store.add_embeddings(embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings, chunk_datas)
    
    # Save
    index_dir = DATA / "faiss_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    store.save(index_dir)
    
    size_kb = (index_dir / "faiss.index").stat().st_size / 1024
    print(f"\n✅ Index saved: {index_dir}")
    print(f"   {store.size} chunks, {embedder.dimension}-dim vectors")
    print(f"   Index: {size_kb:.0f} KB")

if __name__ == "__main__":
    main()
