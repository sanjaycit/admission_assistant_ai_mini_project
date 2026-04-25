# College Admission Information System

A modular Python application that scrapes college websites, extracts admission information, and provides a query system using RAG (Retrieval-Augmented Generation).

## Project Structure

```
admission_project/
├── config.py              # Configuration constants and settings
├── data_loader.py         # CSV loading and data processing functions
├── web_scraper.py         # Web scraping and content extraction
├── vector_store.py        # Vector database operations (FAISS)
├── query_engine.py        # Query processing and LLM operations
├── main.py               # Main pipeline orchestration
├── requirements.txt       # Python dependencies
└── colleges_chennai.csv   # College data (input)
```

## Features

- **Modular Architecture**: Separated concerns into logical modules
- **Web Scraping**: Extracts admission information from college websites
- **Vector Database**: Stores processed content using FAISS for efficient retrieval
- **RAG System**: Uses LangChain and Ollama for intelligent question answering
- **Configurable**: Easy to modify settings through config.py

## Installation

1. Create a virtual environment:
```bash
python -m venv .venv
```

2. Activate the virtual environment:
```bash
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Run the full pipeline:
```bash
python main.py
```

### Inspect the vector database:
```bash
python main.py inspect
```

### Query the system:
```bash
python main.py query "What are the admission requirements for IIT Madras?"
```

## Configuration

Modify `config.py` to change:
- LLM models (EMBED_MODEL, LLM_MODEL)
- Processing limits (MAX_COLLEGES)
- HTTP settings (TIMEOUT, MAX_RETRIES)
- Vector database settings (CHUNK_SIZE, SIMILARITY_K)

## Requirements

- Python 3.8+
- Ollama running locally with required models:
  - `nomic-embed-text` for embeddings
  - `gemma:2b` for question answering (or your preferred model)