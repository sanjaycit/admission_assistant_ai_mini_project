# config.py - Configuration constants and settings

import os
from pathlib import Path

# Get the backend root directory
BACKEND_ROOT = Path(__file__).parent.parent.parent

# HTTP settings
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_RETRIES = 3
TIMEOUT = 10

# LLM settings
EMBED_MODEL = "nomic-embed-text"  # Ollama — stays local for embeddings
# LLM_MODEL = "gemma:2b"               # Ollama local model (too small for grounding)
# GEMINI_MODEL = "gemini-2.0-flash"    # quota exhausted on free tier
GEMINI_MODEL = "gemini-2.5-flash"  # works on v1beta endpoint langchain uses

# File paths
DEFAULT_CSV_PATH = str(BACKEND_ROOT / "data" / "raw" / "colleges_chennai.csv")
VECTOR_DB_PATH = str(BACKEND_ROOT / "data" / "chroma_db")

# Processing settings
MAX_COLLEGES = None  # Process all colleges

# --- Chunk Quality (Fix 2) ---
# Smaller chunks = more precise, fact-focused retrieval
CHUNK_SIZE = 350          # ~300-400 tokens; tight paragraph-level chunks
CHUNK_OVERLAP = 80        # Overlap preserves sentence boundaries across chunks

# --- Retrieval Width (Fix 4) ---
# Retrieve more candidates and let the reranker filter to the best
SIMILARITY_K = 8          # Fetch 8 candidates → reranker picks top 3
RERANK_TOP_N = 3          # Final chunks passed to LLM