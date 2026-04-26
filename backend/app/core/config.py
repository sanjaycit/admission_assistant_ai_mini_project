# config.py - Configuration constants and settings

# LLM settings
# EMBED_MODEL = "nomic-embed-text"  # Ollama — stays local for embeddings
EMBED_MODEL = "models/text-embedding-004" # Gemini embedding model
GEMINI_MODEL = "gemini-2.5-flash"  # works on v1beta endpoint langchain uses
# LLM_MODEL = "gemma:2b"               # Ollama local model (too small fo

# --- Chunk Quality (Fix 2) ---
# Smaller chunks = more precise, fact-focused retrieval
CHUNK_SIZE = 350          # ~300-400 tokens; tight paragraph-level chunks
CHUNK_OVERLAP = 80        # Overlap preserves sentence boundaries across chunks

# --- Retrieval Width (Fix 4) ---
# Retrieve more candidates and let the reranker filter to the best
SIMILARITY_K = 8          # Fetch 8 candidates → reranker picks top 3
RERANK_TOP_N = 3          # Final chunks passed to LLM