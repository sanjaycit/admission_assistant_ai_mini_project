import os
import time
from typing import Dict, Tuple, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from app.core.config import EMBED_MODEL, SIMILARITY_K, CHUNK_SIZE, CHUNK_OVERLAP, RERANK_TOP_N

# Define persistent storage path
PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_cache")

# Freshness: cached chunks older than this (in seconds) are considered stale
# 24 hours — fees/rankings change, so daily refresh is reasonable
CACHE_TTL_SECONDS = 86_400

# Fix 6: Extended keyword set for hybrid retrieval boost
# Grouped by category so it's easy to expand later
BOOST_KEYWORDS = {
    # Financial facts
    "financial": ["$", "usd", "fee", "cost", "tuition", "price", "amount", "pay",
                  "scholarship", "aid", "grant", "loan", "waiver", "refund", "deposit"],
    # Ranking facts
    "ranking": ["rank", "ranked", "#", "top", "position", "tier", "best"],
    # Deadline facts
    "deadline": ["deadline", "due", "apply by", "closes", "open", "date", "round"],
    # Admission stats
    "stats": ["rate", "accepted", "admit", "gpa", "sat", "act", "score", "average"],
}
# Flatten for quick lookup, but keep category weights
KEYWORD_WEIGHTS = {}
for category, words in BOOST_KEYWORDS.items():
    for w in words:
        KEYWORD_WEIGHTS[w] = KEYWORD_WEIGHTS.get(w, 0) + 0.25  # 0.25 boost per hit


def get_db() -> Chroma:
    """Initialize and return the persistent ChromaDB."""
    # Fix 2: Use a dedicated, better embedding model for retrieval quality
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    return Chroma(
        collection_name="web_cache",
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR
    )


def _is_fresh(metadata: dict) -> bool:
    """Fix 5: Check if a cached chunk is still within its TTL."""
    cached_at = metadata.get("cached_at")
    if cached_at is None:
        return True  # Legacy chunks without timestamp pass through (treat as fresh)
    return (time.time() - float(cached_at)) < CACHE_TTL_SECONDS


def search_db(
    query: str,
    threshold: float = 1.2,
    k: int = SIMILARITY_K,
    require_fresh: bool = False,
) -> Optional[Tuple[str, List[str]]]:
    """
    Search the persistent DB.

    Fix 4: Retrieve k=8 candidates, then rerank and return top RERANK_TOP_N.
    Fix 5: Optionally filter stale chunks (require_fresh=True skips old data).
    Fix 6: Keyword-weighted hybrid reranking.

    Returns (context, sources) if relevant chunks are found, otherwise None.
    """
    print(f"  [DB] Checking persistent cache for relevant context...")
    db = get_db()

    # Check if DB is completely empty
    if db._collection.count() == 0:
        print("  [DB] Cache is empty.")
        return None

    # Fix 4: Pull k=8 candidates (wider net)
    results = db.similarity_search_with_score(query, k=k)

    # Filter by distance threshold
    relevant_docs = [(doc, score) for doc, score in results if score < threshold]

    if not relevant_docs:
        print(f"  [DB] No relevant data found below threshold {threshold}.")
        return None

    # Fix 5: Freshness check
    if require_fresh:
        fresh_docs = [(doc, score) for doc, score in relevant_docs if _is_fresh(doc.metadata)]
        stale_count = len(relevant_docs) - len(fresh_docs)
        if stale_count > 0:
            print(f"  [DB] Dropped {stale_count} stale chunk(s) (older than {CACHE_TTL_SECONDS // 3600}h).")
        relevant_docs = fresh_docs

    if not relevant_docs:
        print("  [DB] All cached chunks are stale. Proceeding to web search.")
        return None

    print(f"  [DB] Found {len(relevant_docs)} candidate chunk(s). Running keyword reranker...")

    # Fix 6: Hybrid reranking — semantic score + keyword boost
    reranked = []
    for doc, l2_distance in relevant_docs:
        # Convert L2 distance → similarity score (higher is better)
        base_score = threshold - l2_distance

        # Keyword boost: accumulate weighted hits
        content_lower = doc.page_content.lower()
        keyword_boost = sum(
            weight for keyword, weight in KEYWORD_WEIGHTS.items()
            if keyword in content_lower
        )

        # Cap boost to avoid swamping semantic score
        capped_boost = min(keyword_boost, 1.5)
        final_score = base_score + capped_boost

        reranked.append((final_score, doc))

    # Sort descending and take top RERANK_TOP_N
    reranked.sort(key=lambda x: x[0], reverse=True)
    top_docs = [doc for _, doc in reranked[:RERANK_TOP_N]]

    print(f"  [DB] Reranked → serving top {len(top_docs)} chunk(s) to LLM.")

    context_parts = []
    sources = set()
    for doc in top_docs:
        context_parts.append(doc.page_content)
        sources.add(doc.metadata.get("source", "Unknown Source"))

    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)


def add_to_db(texts_by_url: Dict[str, str]):
    """
    Fix 2: Chunk texts with paragraph-first splitting and store in ChromaDB.
    Fix 5: Attach a cached_at timestamp to every chunk for freshness checks.
    """
    print(f"  [DB] Saving fetched content to persistent cache...")

    # Fix 2: Paragraph-level splitting first, then sentence, then word
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        # Priority: paragraph → sentence → clause → word
        separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )

    documents = []
    metadatas = []
    now = str(time.time())  # Fix 5: freshness timestamp

    for url, text in texts_by_url.items():
        if not text:
            continue
        chunks = splitter.split_text(text)
        for chunk in chunks:
            # Skip chunks that are too short to be useful (likely navigation junk)
            if len(chunk.strip()) < 60:
                continue
            documents.append(chunk)
            metadatas.append({"source": url, "cached_at": now})

    if not documents:
        print("  [DB] No valid chunks to store.")
        return

    db = get_db()
    db.add_texts(texts=documents, metadatas=metadatas)
    print(f"  [DB] Successfully cached {len(documents)} chunks.")
