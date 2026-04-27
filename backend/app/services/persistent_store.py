"""
Module managing Vector storage (ChromaDB), caching, and distance-based document retrieval.
"""
import os
import time
from typing import Dict, Tuple, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import EMBED_MODEL, SIMILARITY_K, CHUNK_SIZE, CHUNK_OVERLAP, GEMINI_MODEL

# Define persistent storage path
PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_cache")

# Cache expiration time in seconds (Default: 24 hours).
# Ensures information like fees and rankings remain up-to-date.
CACHE_TTL_SECONDS = 86_400


def get_db() -> Chroma:
    """Initialize and return the persistent ChromaDB."""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    # embeddings = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)
    return Chroma(
        collection_name="web_cache",
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR
    )


def _is_fresh(metadata: dict) -> bool:
    """Check if a cached chunk is still within its TTL."""
    cached_at = metadata.get("cached_at")
    if cached_at is None:
        return True  # Legacy chunks without timestamp pass through
    return (time.time() - float(cached_at)) < CACHE_TTL_SECONDS


def search_db(
    query: str,
    entity: Optional[str] = None,
    threshold: float = 1.2,
    k: int = SIMILARITY_K,
    require_fresh: bool = False,
) -> Optional[Tuple[str, List[str]]]:
    """
    Entity-aware search of the persistent ChromaDB cache.

    If an entity is provided, the retrieval is filtered to only that college's chunks.
    This strictly prevents cross-college data contamination.

    Returns:
        Optional[Tuple[str, List[str]]]: A tuple of formatting context and source URLs if found.
    """
    entity_label = f"'{entity}'" if entity else "any"
    print(f"  [DB] Checking persistent cache for relevant context (entity={entity_label})...")
    db = get_db()

    if db._collection.count() == 0:
        print("  [DB] Cache is empty.")
        return None

    # Filter retrieval by entity to prevent cross-contamination of college data
    where_filter = {"college": {"$eq": entity}} if entity else None

    try:
        results = db.similarity_search_with_score(query, k=k, filter=where_filter)
    except Exception as e:
        # Graceful fallback: if filter fails (e.g. legacy collection), search unfiltered
        print(f"  [DB] Filter error ({e}), falling back to unfiltered search.")
        results = db.similarity_search_with_score(query, k=k)

    # Filter by distance threshold
    relevant_docs = [(doc, score) for doc, score in results if score < threshold]

    if not relevant_docs:
        print(f"  [DB] No relevant data found below threshold {threshold}.")
        return None

    # Freshness check
    if require_fresh:
        fresh_docs = [(doc, score) for doc, score in relevant_docs if _is_fresh(doc.metadata)]
        stale_count = len(relevant_docs) - len(fresh_docs)
        if stale_count > 0:
            print(f"  [DB] Dropped {stale_count} stale chunk(s) (older than {CACHE_TTL_SECONDS // 3600}h).")
        relevant_docs = fresh_docs

    if not relevant_docs:
        print("  [DB] All cached chunks are stale. Proceeding to web search.")
        return None

    print(f"  [DB] Found {len(relevant_docs)} candidate chunk(s).")
    
    # We no longer run LLM reranker; just take the top K documents
    top_docs = [doc for doc, _ in relevant_docs]

    context_parts = []
    sources = set()
    seen_content = set()  # deduplicate identical chunks

    for doc in top_docs:
        fingerprint = " ".join(doc.page_content.split())
        if fingerprint in seen_content:
            continue
        seen_content.add(fingerprint)
        context_parts.append(doc.page_content)
        sources.add(doc.metadata.get("source", "Unknown Source"))

    if not context_parts:
        return None

    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)


def add_to_db(texts_by_url: Dict[str, str], entity: Optional[str] = None):
    """
    Splits the extracted texts into chunks and stores them in ChromaDB.
    Associates each chunk with an optional entity name to enable filtered retrieval.
    """
    print(f"  [DB] Saving fetched content to persistent cache (entity='{entity}')...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n# ", "\n## ", "\n### ", "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )

    documents = []
    metadatas = []
    now = str(time.time())

    for url, text in texts_by_url.items():
        if not text:
            continue
        chunks = splitter.split_text(text)
        for chunk in chunks:
            if len(chunk.strip()) < 60:
                continue
            documents.append(chunk)
            metadata = {"source": url, "cached_at": now}
            if entity:
                metadata["college"] = entity
            metadatas.append(metadata)

    if not documents:
        print("  [DB] No valid chunks to store.")
        return

    db = get_db()
    db.add_texts(texts=documents, metadatas=metadatas)
    print(f"  [DB] Successfully cached {len(documents)} chunks tagged with entity='{entity}'.")
