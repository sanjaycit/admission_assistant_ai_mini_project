"""
debug_pipeline.py — Pipeline Diagnostic Tool
=============================================
Run this to find EXACTLY where the RAG pipeline is failing.

Usage:
    python debug_pipeline.py

Stages checked:
    Stage 1 — Raw HTML fetch
    Stage 2 — Text extraction (trafilatura)
    Stage 3 — Chunking
    Stage 4 — What's stored in ChromaDB
    Stage 5 — Retrieval accuracy (multiple query variants)
"""

import sys
from pathlib import Path

# Ensure package is importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncio
import requests
import trafilatura
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ─── Config ────────────────────────────────────────────────────────────────────
TEST_URLS = [
    "https://facts.mit.edu/undergraduate-admissions/undergraduate-tuition/",
    "https://studyabroad.careers360.com/articles/massachusetts-institute-of-technology-fees",
]
TEST_QUERIES = [
    "MIT admission fee",
    "MIT application fee",
    "MIT tuition cost",
    "Massachusetts Institute of Technology fee",
]
CHUNK_SIZE   = 350
CHUNK_OVERLAP = 80
SEPARATOR = "\n" + "─" * 60 + "\n"


# ─── Helpers ───────────────────────────────────────────────────────────────────
def banner(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")

def result(label: str, value):
    status = "[OK]" if value else "[FAIL]"
    print(f"  {status}  {label}: {value}")


# ─── Stage 1: Raw HTML ─────────────────────────────────────────────────────────
banner("STAGE 1 — Raw HTML Fetch")
raw_htmls = {}
for url in TEST_URLS:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            raw_htmls[url] = r.text
            print(f"  [OK]  {url}")
            print(f"       HTML size: {len(r.text):,} bytes")
        else:
            print(f"  [FAIL]  {url}  →  HTTP {r.status_code}")
            raw_htmls[url] = ""
    except Exception as e:
        print(f"  [FAIL]  {url}  →  {e}")
        raw_htmls[url] = ""


# ─── Stage 2: Text Extraction ──────────────────────────────────────────────────
banner("STAGE 2 — Text Extraction (trafilatura)")
extracted_texts = {}
for url, html in raw_htmls.items():
    if not html:
        extracted_texts[url] = ""
        continue
    text = trafilatura.extract(
        html,
        include_links=False,
        include_images=False,
        include_comments=False,
    ) or ""
    extracted_texts[url] = text

    print(f"\n  URL: {url}")
    print(f"  Extracted length: {len(text):,} chars")

    # Key diagnostic: does the raw extracted text contain fee info?
    fee_present   = any(kw in text.lower() for kw in ["fee", "tuition", "cost", "$"])
    dollar_present = "$" in text

    result("Fee keyword present in raw text", fee_present)
    result("Dollar sign ($) present        ", dollar_present)

    if text:
        print("\n  ── First 1500 chars of extracted text ──")
        print(text[:1500])
        print("  [... truncated ...]")

        # Search for fee-related sentences
        print("\n  ── Lines containing 'fee' or '$' ──")
        hits = [line.strip() for line in text.splitlines() if "fee" in line.lower() or "$" in line]
        if hits:
            for h in hits[:10]:
                print(f"    >  {h}")
        else:
            print("    [FAIL]  NONE FOUND — extraction is likely the culprit!")
    else:
        print("  [FAIL]  EMPTY TEXT — trafilatura extracted nothing!")


# ─── Stage 3: Chunking ─────────────────────────────────────────────────────────
banner("STAGE 3 — Chunking")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
)

all_chunks = {}
for url, text in extracted_texts.items():
    if not text:
        all_chunks[url] = []
        continue
    chunks = splitter.split_text(text)
    # Filter short junk
    chunks = [c for c in chunks if len(c.strip()) >= 60]
    all_chunks[url] = chunks

    print(f"\n  URL: {url}")
    print(f"  Total chunks: {len(chunks)}")

    # Find chunks with fee info
    fee_chunks = [c for c in chunks if any(kw in c.lower() for kw in ["fee", "tuition", "$", "cost"])]
    result(f"Chunks containing fee info", len(fee_chunks) > 0)
    print(f"  Fee-relevant chunks: {len(fee_chunks)} / {len(chunks)}")

    if fee_chunks:
        print("\n  ── Top fee-relevant chunks ──")
        for i, fc in enumerate(fee_chunks[:3], 1):
            print(f"  [{i}] {fc[:300]}")
            print(SEPARATOR)
    else:
        print("  [FAIL]  NO FEE CHUNKS FOUND — chunking is eating the answer!")
        print("\n  ── First 5 chunks (for inspection) ──")
        for i, c in enumerate(chunks[:5], 1):
            print(f"  [{i}] {c[:200]}")
            print(SEPARATOR)


# ─── Stage 4: What's in ChromaDB ──────────────────────────────────────────────
banner("STAGE 4 — ChromaDB Stored Documents")
try:
    from app.services.persistent_store import get_db
    db = get_db()
    count = db._collection.count()
    print(f"  Total documents in DB: {count}")

    if count == 0:
        print("  [FAIL]  DB is EMPTY — nothing has been stored yet!")
        print("  [INFO]   Run 'python main.py query \"MIT fee\"' first, then re-run this script.")
    else:
        # Broad fetch to see what's there
        raw_results = db.similarity_search("fee cost tuition", k=10)
        fee_docs = [d for d in raw_results if any(kw in d.page_content.lower() for kw in ["fee", "$", "tuition", "cost"])]

        result(f"Fee-relevant docs in top-10 DB results", len(fee_docs) > 0)
        print(f"  Fee docs found: {len(fee_docs)} / {len(raw_results)}")

        print("\n  ── All top-10 DB results ──")
        for i, doc in enumerate(raw_results, 1):
            print(f"  [{i}] source: {doc.metadata.get('source', 'unknown')}")
            print(f"       {doc.page_content[:250]}")
            print(SEPARATOR)

except Exception as e:
    print(f"  [FAIL]  Could not access DB: {e}")


# ─── Stage 5: Retrieval Accuracy ───────────────────────────────────────────────
banner("STAGE 5 — Retrieval (Query Variants)")
try:
    from app.services.persistent_store import get_db
    db = get_db()

    if db._collection.count() == 0:
        print("  [FAIL]  DB empty — skipping retrieval test.")
    else:
        for q in TEST_QUERIES:
            results = db.similarity_search_with_score(q, k=5)
            best_score = results[0][1] if results else None
            best_text  = results[0][0].page_content[:200] if results else ""
            fee_in_top = any(
                any(kw in doc.page_content.lower() for kw in ["fee", "$", "tuition", "cost"])
                for doc, _ in results
            )

            print(f"\n  Query: '{q}'")
            print(f"  Best L2 score: {best_score:.4f}" if best_score else "  No results")
            result("Fee info in top-5 results", fee_in_top)
            print(f"  Best chunk: {best_text[:200]}")

except Exception as e:
    print(f"  [FAIL]  Retrieval test failed: {e}")


# ─── Verdict ──────────────────────────────────────────────────────────────────
banner("DIAGNOSIS SUMMARY")
print("""
  Run the stages in order and look for the first [FAIL]:

  Stage 1 [FAIL]  → Network issue (URL blocked or timeout)
  Stage 2 [FAIL]  → Extraction issue (trafilatura not finding content)
  Stage 3 [FAIL]  → Chunking destroys answer (try smaller chunks)
  Stage 4 [FAIL]  → DB empty or chunks don't contain fee info (store quality)
  Stage 5 [FAIL]  → Retrieval mismatch (embedding space / query mismatch)

  If all [OK] → issue is in the LLM prompt or context assembly.
""")
