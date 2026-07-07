"""
Batch download and index all available Moose documents from mooseintl.org.

Downloads key PDFs, runs the ingestion pipeline on each, builds a combined FAISS index.
"""
import sys, os, urllib.request, json, time, argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT_ROOT / "backend"
DATA = PROJECT_ROOT / "data"
sys.path.insert(0, str(BACKEND))

# All known Moose PDFs from mooseintl.org
DOCUMENTS = [
    # Tier 1 - Supreme Governing
    {"url": "https://www.mooseintl.org/wp-content/uploads/2025/07/Aug-2025-General-Laws.pdf",
     "title": "General Laws of the Moose Fraternity", "doc_type": "general_laws", "tier": 1},
    
    # Tier 3 - Operational
    {"url": "https://www.mooseintl.org/wp-content/uploads/2021/06/2023-Officer-Committeemen-Handbook.pdf",
     "title": "Officer & Committeemen Handbook", "doc_type": "officer_handbook", "tier": 3},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2025/08/2025-Social-Quarters-Rules-Regulations.pdf",
     "title": "Social Quarters Rules & Regulations", "doc_type": "social_quarters_rules", "tier": 3},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2025/12/2026-Lodge-Election-Handbook.pdf",
     "title": "Lodge Election Handbook", "doc_type": "election_handbook", "tier": 3},
    
    # Tier 5 - WOTM
    {"url": "https://www.mooseintl.org/wp-content/uploads/2021/03/WOTM-General-Laws-2021.pdf",
     "title": "Women of the Moose General Laws", "doc_type": "wotm_general_laws", "tier": 5},
    
    # Tier 7 - Programs
    {"url": "https://www.mooseintl.org/wp-content/uploads/2025/04/2024-Activities-Guidebook.pdf",
     "title": "Activities Guidebook", "doc_type": "activities_guidebook", "tier": 7},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2025/09/2025-Jr-Moose-Guidelines.pdf",
     "title": "Jr Moose Guidelines", "doc_type": "youth_program", "tier": 7},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2024/08/2024-YA-Guidebook.pdf",
     "title": "Young Adults Guidebook", "doc_type": "youth_program", "tier": 7},
    
    # Tier 3 - More operational
    {"url": "https://www.mooseintl.org/wp-content/uploads/2023/06/2023-Association-Rules-Order-Report.pdf",
     "title": "Association Rules & Order", "doc_type": "meeting_procedure", "tier": 3},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2021/07/2022-YA-Memo-Student-Rules.pdf",
     "title": "YA Student Rules", "doc_type": "youth_program", "tier": 7},
    
    # Activity guidelines
    {"url": "http://www.mooseintl.org/wp-content/uploads/2014/08/2021-Moose-Riders-Guidelines.pdf",
     "title": "Moose Riders Guidelines", "doc_type": "activity_guidelines", "tier": 7},
    {"url": "https://www.mooseintl.org/wp-content/uploads/2021/04/Valued-Veterans-Activity-Group-Guidelines.pdf",
     "title": "Valued Veterans Activity Group Guidelines", "doc_type": "activity_guidelines", "tier": 7},
]

def download(url, path):
    if path.exists():
        print(f"  Already downloaded: {path.name}")
        return True
    try:
        print(f"  Downloading: {path.name}...")
        urllib.request.urlretrieve(url, str(path))
        size_mb = path.stat().st_size / 1e6
        print(f"  Saved: {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--index-only", action="store_true")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    pdf_dir = DATA / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    
    # Step 1: Download all PDFs
    if not args.index_only:
        print("=" * 60)
        print("  DOWNLOADING DOCUMENTS")
        print("=" * 60)
        downloaded = []
        for i, doc in enumerate(DOCUMENTS):
            print(f"\n[{i+1}/{len(DOCUMENTS)}] {doc['title']}")
            filename = doc["url"].split("/")[-1]
            path = pdf_dir / filename
            if download(doc["url"], path):
                downloaded.append({**doc, "path": str(path)})
        print(f"\n  Downloaded: {len(downloaded)}/{len(DOCUMENTS)}")
    
    # Step 2: Run build_index.py for combined index
    if not args.download_only:
        print("\n" + "=" * 60)
        print("  BUILDING COMBINED INDEX")
        print("=" * 60)
        
        from app.core.ingestion.pipeline import IngestionPipeline
        from app.core.retrieval.vector_store import FAISSVectorStore, LocalEmbedder
        
        all_chunks = []
        pdf_files = list(pdf_dir.glob("*.pdf"))
        print(f"\n  Found {len(pdf_files)} PDFs to process")
        
        for pdf_path in pdf_files:
            print(f"\n  Processing: {pdf_path.name}")
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(pdf_path))
            
            if result.status == "error":
                print(f"    ❌ Failed: {result.errors[:2]}")
                continue
            
            chunks = result.metadata.get("chunks", [])
            if chunks:
                # Tag chunks with document metadata
                for c in chunks:
                    c.document_short_title = result.metadata.get("classification", {}).__class__.__name__ if hasattr(result.metadata.get("classification", {}), '__class__') else pdf_path.stem[:40]
                    c.document_tier = result.tier
                all_chunks.extend(chunks)
                print(f"    ✅ {len(chunks)} chunks (Tier {result.tier})")
        
        if not all_chunks:
            print("\n  No chunks to index!")
            return
        
        print(f"\n  Total chunks: {len(all_chunks)}")
        
        # Generate embeddings
        print(f"\n  Generating embeddings...")
        embedder = LocalEmbedder("all-MiniLM-L6-v2")
        all_chunks = embedder.embed_chunks(all_chunks, show_progress=True)
        
        # Build combined FAISS index
        print(f"\n  Building FAISS index...")
        store = FAISSVectorStore(dimension=embedder.dimension)
        store.add_chunks(all_chunks)
        
        # Save
        index_dir = DATA / "faiss_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        store.save(index_dir)
        
        print(f"\n  ✅ Index saved: {index_dir}")
        print(f"     {store.size} chunks, {embedder.dimension}-dim vectors")
        print(f"     Total documents processed: {len(pdf_files)}")

if __name__ == "__main__":
    main()
