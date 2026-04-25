from typing import Dict, Tuple, List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from app.core.config import LLM_MODEL, SIMILARITY_K

def build_ephemeral_index(texts_by_url: Dict[str, str]):
    """Chunk texts, embed, and store in an ephemeral Chroma index."""
    print(f"  [INDEX] Building ephemeral vector index...")
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len
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
        return None

    embeddings = OllamaEmbeddings(model=LLM_MODEL)
    
    vectorstore = Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        metadatas=metadatas
    )
    
    return vectorstore

def retrieve_context(vectorstore, query: str, k: int = SIMILARITY_K) -> Tuple[str, List[str]]:
    """Retrieve top k relevant chunks from the ephemeral store."""
    print(f"  [RETRIEVE] Retrieving most relevant context...")
    docs = vectorstore.similarity_search(query, k=k)
    
    context_parts = []
    sources = set()
    
    for doc in docs:
        context_parts.append(doc.page_content)
        sources.add(doc.metadata.get("source", "Unknown Source"))
        
    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)
