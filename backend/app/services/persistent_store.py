import os
from typing import Dict, Tuple, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from app.core.config import LLM_MODEL, SIMILARITY_K, CHUNK_SIZE, CHUNK_OVERLAP

# Define persistent storage path
PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_cache")

def get_db() -> Chroma:
    """Initialize and return the persistent ChromaDB."""
    embeddings = OllamaEmbeddings(model=LLM_MODEL)
    return Chroma(
        collection_name="web_cache",
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR
    )

def search_db(query: str, threshold: float = 1.2, k: int = SIMILARITY_K) -> Optional[Tuple[str, List[str]]]:
    """
    Search the persistent DB.
    Returns (context, sources) if highly relevant chunks are found.
    Otherwise returns None.
    """
    print(f"  [DB] Checking persistent cache for relevant context...")
    db = get_db()
    
    # Check if DB is completely empty
    if db._collection.count() == 0:
        print("  [DB] Cache is empty.")
        return None
        
    # similarity_search_with_score returns (Document, distance)
    # Distance is L2 distance by default. Lower is better.
    results = db.similarity_search_with_score(query, k=k)
    
    # Filter by threshold
    relevant_docs = [doc for doc, score in results if score < threshold]
    
    if not relevant_docs:
        print(f"  [DB] No relevant data found below threshold {threshold}.")
        return None
        
    print(f"  [DB] Found {len(relevant_docs)} highly relevant chunks! Bypassing web search.")
    
    # Hybrid Retrieval (Keyword Boosting)
    reranked_docs = []
    boost_keywords = ["$", "usd", "fee", "cost", "tuition", "price", "amount", "pay"]
    
    for doc, l2_distance in relevant_docs:
        # Lower distance is better. We convert distance to a score where higher is better.
        # Simple inversion: score = threshold - distance (so max score is threshold, min is 0)
        base_score = threshold - l2_distance
        
        # Keyword Boost
        content_lower = doc.page_content.lower()
        keyword_hits = sum(1 for kw in boost_keywords if kw in content_lower)
        
        # Boost score by 0.3 per keyword hit (arbitrary weight)
        boosted_score = base_score + (keyword_hits * 0.3)
        
        reranked_docs.append((boosted_score, doc))
        
    # Sort by boosted score descending and take top 4
    reranked_docs.sort(key=lambda x: x[0], reverse=True)
    top_docs = [doc for score, doc in reranked_docs[:4]]
    
    print(f"  [DB] Filtered down to top {len(top_docs)} chunks after keyword reranking.")
    
    context_parts = []
    sources = set()
    
    for doc in top_docs:
        context_parts.append(doc.page_content)
        sources.add(doc.metadata.get("source", "Unknown Source"))
        
    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)

def add_to_db(texts_by_url: Dict[str, str]):
    """Chunk texts and append them to the persistent Chroma index."""
    print(f"  [DB] Saving fetched content to persistent cache...")
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    documents = []
    metadatas = []
    
    for url, text in texts_by_url.items():
        if not text:
            continue
        chunks = splitter.split_text(text)
        for chunk in chunks:
            documents.append(chunk)
            metadatas.append({"source": url})

    if not documents:
        print("  [DB] No valid chunks to store.")
        return

    db = get_db()
    db.add_texts(texts=documents, metadatas=metadatas)
    print(f"  [DB] Successfully cached {len(documents)} chunks.")
