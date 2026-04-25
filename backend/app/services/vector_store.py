# vector_store.py - Vector database operations

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from app.core.config import EMBED_MODEL, VECTOR_DB_PATH, CHUNK_SIZE, CHUNK_OVERLAP

def chunk_text(text):
    """Split text into manageable chunks"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    return splitter.split_text(text)

def build_documents(college, url, text):
    """Create Document objects from scraped content"""
    chunks = chunk_text(text)

    docs = []
    for chunk in chunks:
        docs.append(Document(
            page_content=chunk,
            metadata={
                "college": college,
                "source": url
            }
        ))

    return docs

def store_vector_db(documents):
    """Store documents in FAISS vector database"""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    db = FAISS.from_documents(documents, embeddings)
    db.save_local(VECTOR_DB_PATH)
    return db

def update_vector_db(documents):
    """Add documents to existing FAISS vector database or create new one if it doesn't exist"""
    import os
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    
    try:
        # Try to load existing database
        if os.path.exists(VECTOR_DB_PATH):
            db = load_vector_db()
            # Add new documents to existing database
            db.add_documents(documents)
            db.save_local(VECTOR_DB_PATH)
            return db
    except Exception as e:
        print(f"  Could not load existing database: {e}. Creating new one...")
    
    # If database doesn't exist or failed to load, create new one
    db = FAISS.from_documents(documents, embeddings)
    db.save_local(VECTOR_DB_PATH)
    return db

def load_vector_db():
    """Load existing FAISS vector database"""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
    return db

def inspect_vector_db():
    """Inspect the contents of the vector database"""
    try:
        db = load_vector_db()

        # Get all documents from the vector store
        all_docs = db.similarity_search("", k=1000)  # Large k to get all docs

        print(f"\n=== VECTOR DATABASE INSPECTION ===")
        print(f"Total documents stored: {len(all_docs)}")

        # Group by college
        colleges = {}
        for doc in all_docs:
            college = doc.metadata.get('college', 'Unknown')
            if college not in colleges:
                colleges[college] = []
            colleges[college].append(doc)

        print(f"Colleges processed: {len(colleges)}")
        print("\nColleges and document counts:")
        for college, docs in colleges.items():
            print(f"  {college}: {len(docs)} documents")

        print("\n=== SAMPLE DOCUMENTS ===")
        for i, doc in enumerate(all_docs[:5]):  # Show first 5 documents
            print(f"\nDocument {i+1}:")
            print(f"College: {doc.metadata.get('college', 'Unknown')}")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print(f"Content preview: {doc.page_content[:200]}...")

        return all_docs

    except Exception as e:
        print(f"Error inspecting vector database: {e}")
        return None

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        inspect_vector_db()
    else:
        print("Usage: python vector_store.py inspect")
        print("This will show the contents of the vector database.")