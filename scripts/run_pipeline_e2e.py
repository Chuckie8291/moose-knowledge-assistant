"""
End-to-end test: Download the real Moose General Laws PDF and run
the full ingestion pipeline on it.

Verifies:
  1. PDF download + loading
  2. Document classification
  3. Structure extraction (chapters, articles, sections)
  4. Chunking with citation headers
  5. Embedding generation (stub — requires API key)
"""

import sys, os, hashlib, json, urllib.request
from pathlib import Path

BACKEND = r"C:\Users\Chuck\Desktop\Ask Anything moose\backend"
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

# ── Step 1: Download General Laws PDF ─────────────────────
PDF_URL = "https://www.mooseintl.org/wp-content/uploads/2025/07/Aug-2025-General-Laws.pdf"
DOWNLOAD_DIR = Path(r"C:\Users\Chuck\Desktop\Ask Anything moose\data")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = DOWNLOAD_DIR / "Aug-2025-General-Laws.pdf"

if not PDF_PATH.exists():
    print(f"Downloading General Laws PDF...")
    print(f"  URL: {PDF_URL}")
    urllib.request.urlretrieve(PDF_URL, str(PDF_PATH))
    print(f"  Saved: {PDF_PATH} ({PDF_PATH.stat().st_size / 1e6:.1f} MB)")
else:
    print(f"PDF already downloaded: {PDF_PATH} ({PDF_PATH.stat().st_size / 1e6:.1f} MB)")

# ── Step 2: Load document ────────────────────────────────
print("\n--- STAGE 1-2: LOAD + CLASSIFY ---")
from app.core.ingestion.document_loader import DocumentLoader
from app.core.ingestion.classifier import DocumentClassifier

loader = DocumentLoader()
loaded = loader.load(str(PDF_PATH))
print(f"  Pages: {loaded.total_pages}")
print(f"  Characters: {loaded.total_chars:,}")
print(f"  Digital: {loaded.is_digital}")
print(f"  Content hash: {loaded.content_hash[:16]}...")

classifier = DocumentClassifier()
preview = loader.load_preview(str(PDF_PATH))
classification = classifier.classify(preview_text=preview, filename=str(PDF_PATH))
print(f"  Classification: {classification.label} (Tier {classification.tier})")
print(f"  Confidence: {classification.confidence:.0%}")
print(f"  Citation format: {classification.citation_format}")

# ── Step 3: Extract structure ────────────────────────────
print("\n--- STAGE 3-5: STRUCTURE + CHUNK ---")
from app.core.ingestion.structure_extractor import get_structure_extractor

# Skip TOC pages (first 5 pages are Table of Contents in Moose GL)
START_PAGE = 6
body_pages = [p for p in loaded.pages if p.page_number >= START_PAGE]
full_text = "\n\n".join(p.text for p in body_pages)

# Build page map from body pages only
page_map = {}
char_pos = 0
for page in body_pages:
    page_map[char_pos] = page.page_number
    char_pos += len(page.text) + 2

extractor = get_structure_extractor(classification.doc_type)
tree = extractor.extract(full_text, page_map)
all_sections = tree.all_sections()
leaf_sections = tree.leaf_sections()
print(f"  Total sections: {len(all_sections)}")
print(f"  Leaf sections (with content): {len(leaf_sections)}")

# Print first 15 sections for overview, then key Sec. headings
print(f"\n  Section tree (top levels):")
for i, section in enumerate(all_sections[:15]):
    indent = "  " * (section.level - 1)
    print(f"    {indent}L{section.level}: §{section.section_number} — {section.title[:60]}")

if len(all_sections) > 15:
    print(f"    ... ({len(all_sections) - 15} more sections)")

# Show representative Sec. headings (level 4) from across the document
sec_sections = [s for s in all_sections if s.level == 4]
key_sections = ['1.1', '10.1', '17.1', '24.5', '28.1', '44.1', '55.1', '60.1']
print(f"\n  Key Sec. headings (of {len(sec_sections)} total level-4):")
for key in key_sections:
    found = [s for s in sec_sections if s.section_number == key]
    if found:
        s = found[0]
        print(f"    §{key} → {s.hierarchy_path} (p. {s.page_start}) — {s.title[:60]}")
    else:
        print(f"    §{key} → NOT FOUND")

# ── Step 4: Chunk ────────────────────────────────────────
from app.core.ingestion.chunker import get_chunker

chunker = get_chunker(classification.doc_type)
raw_chunks = chunker.chunk(
    tree=tree,
    doc_short_title="General Laws",
    doc_tier=classification.tier,
    effective_date="2025-08-01",
)

# Filter out tiny chunks (page numbers, artifacts)
MIN_CHUNK_TOKENS = 10
chunks = [c for c in raw_chunks if c.token_count >= MIN_CHUNK_TOKENS]
filtered_count = len(raw_chunks) - len(chunks)
if filtered_count:
    print(f"  Filtered {filtered_count} tiny chunks (< {MIN_CHUNK_TOKENS} tokens)")
print(f"\n  Total chunks: {len(chunks)}")

# Stats
total_tokens = sum(c.token_count for c in chunks)
avg_tokens = total_tokens / max(len(chunks), 1)
print(f"  Total tokens: {total_tokens:,}")
print(f"  Avg tokens/chunk: {avg_tokens:.0f}")

# Show sample chunks
print(f"\n  Sample chunks (first 3):")
for i, chunk in enumerate(chunks[:3]):
    print(f"    Chunk {i+1}/{chunk.total_chunks_in_section}:")
    print(f"      Citation: {chunk.citation_header}")
    print(f"      Section: §{chunk.section_number} — {chunk.section_title[:60]}")
    print(f"      Pages: {chunk.page_start}-{chunk.page_end}")
    print(f"      Tokens: {chunk.token_count}")
    text_preview = chunk.content_text[:200].replace('\n', ' ')
    print(f"      Text: {text_preview}...")
    print()

# ── Step 5: Validate ─────────────────────────────────────
print("--- STAGE 6: VALIDATION ---")
errors = []

# Check: every leaf section has at least one chunk
leaf_section_nums = {s.section_number for s in leaf_sections}
chunked_sections = {c.section_number for c in chunks}
unrepresented = leaf_section_nums - chunked_sections
if unrepresented:
    errors.append(f"{len(unrepresented)} leaf sections have no chunks")

# Check: citation headers
no_citation = [c for c in chunks if not c.citation_header.startswith("[SOURCE:")]
if no_citation:
    errors.append(f"{len(no_citation)} chunks missing [SOURCE:] header")

# Check: empty chunks
empty = [c for c in chunks if not c.content_text.strip()]
if empty:
    errors.append(f"{len(empty)} chunks are empty")

# Check: page continuity
pages_covered = set()
for c in chunks:
    for p in range(c.page_start, c.page_end + 1):
        pages_covered.add(p)
page_gaps = set(range(1, loaded.total_pages + 1)) - pages_covered
if page_gaps:
    print(f"  ⚠️  {len(page_gaps)} pages have no chunks (may be blank pages)")
else:
    print(f"  ✅ All {loaded.total_pages} pages covered by chunks")

if errors:
    print(f"\n  ❌ VALIDATION FAILED: {len(errors)} errors")
    for e in errors:
        print(f"     - {e}")
else:
    print(f"\n  ✅ ALL VALIDATION CHECKS PASSED")

# ── Step 6: Save results ─────────────────────────────────
output = {
    "document": {
        "title": "General Laws of the Moose Fraternity",
        "file": str(PDF_PATH),
        "pages": loaded.total_pages,
        "chars": loaded.total_chars,
        "content_hash": loaded.content_hash,
        "classification": {
            "type": classification.doc_type,
            "tier": classification.tier,
            "label": classification.label,
            "confidence": classification.confidence,
        },
    },
    "structure": {
        "total_sections": len(all_sections),
        "leaf_sections": len(leaf_sections),
        "level_counts": {
            "level_1": len([s for s in all_sections if s.level == 1]),
            "level_2": len([s for s in all_sections if s.level == 2]),
            "level_3": len([s for s in all_sections if s.level == 3]),
            "level_4": len([s for s in all_sections if s.level == 4]),
            "level_5": len([s for s in all_sections if s.level == 5]),
            "level_6": len([s for s in all_sections if s.level == 6]),
        },
        "root_sections": [
            {"level": s.level, "number": s.section_number, "title": s.title,
             "pages": f"{s.page_start}-{s.page_end}", "path": s.hierarchy_path}
            for s in tree.root_sections
        ],
        "top_sections": [
            {"level": s.level, "number": s.section_number, "title": s.title,
             "pages": f"{s.page_start}-{s.page_end}", "path": s.hierarchy_path}
            for s in all_sections[:30]
        ],
        "key_sec_headings": [
            {"level": s.level, "number": s.section_number, "title": s.title[:80],
             "pages": f"{s.page_start}-{s.page_end}", "path": s.hierarchy_path}
            for s in all_sections
            if s.level == 4 and s.section_number in
            {'1.1', '10.1', '10.5', '17.1', '20.1', '24.5', '28.1', '44.1', '55.1', '60.1'}
        ],
    },
    "chunks": {
        "total": len(chunks),
        "total_tokens": total_tokens,
        "avg_tokens_per_chunk": round(avg_tokens, 1),
        "sample": [
            {"citation": c.citation_header, "section": c.section_number,
             "title": c.section_title, "pages": f"{c.page_start}-{c.page_end}",
             "tokens": c.token_count, "text_preview": c.content_text[:150]}
            for c in chunks[:5]
        ],
    },
    "validation": {
        "passed": len(errors) == 0,
        "errors": errors,
        "pages_covered": len(pages_covered),
        "total_pages": loaded.total_pages,
    },
}

OUTPUT_PATH = DOWNLOAD_DIR / "pipeline-output-general-laws.json"
OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
print(f"\n  Results saved: {OUTPUT_PATH}")

print("\n✅ End-to-end pipeline test complete.")
