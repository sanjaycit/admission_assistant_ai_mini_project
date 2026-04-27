"""
Configuration constants and settings for the application.
"""

# LLM Models Configuration
# Local option: EMBED_MODEL = "nomic-embed-text"
# Local option: LLM_MODEL = "gemma:2b"
EMBED_MODEL = "models/gemini-embedding-001"
GEMINI_MODEL = "gemini-2.5-flash"

# Text Chunking Configuration
# Smaller chunks provide more precise, fact-focused retrieval
CHUNK_SIZE = 350
CHUNK_OVERLAP = 80

# Retrieval Configuration
# Number of top candidate chunks to fetch from the vector database
SIMILARITY_K = 8