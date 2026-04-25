# rag.py - RAG (Retrieval-Augmented Generation) processing and LLM operations

from langchain_ollama import ChatOllama
from app.core.config import LLM_MODEL, SIMILARITY_K
from app.services.vector_store import load_vector_db

def query_system(question):
    """Query the system using RAG (Retrieval-Augmented Generation)"""
    db = load_vector_db()

    retriever = db.as_retriever(search_kwargs={"k": SIMILARITY_K})
    docs = retriever.invoke(question)

    context = "\n\n".join([d.page_content for d in docs])

    llm = ChatOllama(model=LLM_MODEL)

    prompt = f"""
    You are a helpful assistant that answers questions about college admissions based on the provided context.

    Context from college websites:
    {context}

    Question: {question}

    Answer the question using only the information from the context above. If the context doesn't contain enough information to answer the question, say so clearly.
    """

    response = llm.invoke(prompt)
    return response.content

def get_similar_documents(question, k=None):
    """Get similar documents for a question without generating an answer"""
    if k is None:
        k = SIMILARITY_K

    db = load_vector_db()
    retriever = db.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)

    return docs