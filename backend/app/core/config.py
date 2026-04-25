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
EMBED_MODEL = "nomic-embed-text"  # better for embeddings
LLM_MODEL = "gemma:2b"  # smaller, faster for RAG

# File paths
DEFAULT_CSV_PATH = str(BACKEND_ROOT / "data" / "raw" / "colleges_chennai.csv")
VECTOR_DB_PATH = str(BACKEND_ROOT / "data" / "faiss_index")

# Processing settings
MAX_COLLEGES = 20  # Limit processing to first N colleges
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SIMILARITY_K = 4  # Number of similar documents to retrieve