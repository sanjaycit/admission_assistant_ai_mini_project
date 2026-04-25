import asyncio
from langchain_ollama import ChatOllama
from app.core.config import LLM_MODEL, SIMILARITY_K
from app.services.web_search import normalize_query, search_web
from app.services.web_scraper import fetch_all_urls, clean_html
from app.services.ephemeral_store import build_ephemeral_index, retrieve_context

def generate_answer(query: str, context: str) -> str:
    """Generate final answer using ChatOllama."""
    print(f"  [GENERATE] Generating answer...")
    llm = ChatOllama(model=LLM_MODEL, temperature=0.0)
    
    prompt = f"""
    You are a helpful college admissions assistant.

    Use ONLY the context below to answer the user's question. 
    If the context does not contain the answer, say "I don't have enough information from the web search to answer that." 
    Do NOT guess or use outside knowledge. Keep your answer concise and factual.

    Context:
    {context}

    Question: {query}

    Answer:
    """
    
    response = llm.invoke(prompt)
    return response.content

def query_web_system(query: str) -> str:
    """Main pipeline for Web RAG."""
    # 1. Normalize Query
    clean_query = normalize_query(query)
    
    # 2. Search Web
    search_results = search_web(clean_query, num_results=5)
    urls = [r["url"] for r in search_results if r["url"]]
    
    if not urls:
        return "Sorry, I couldn't find any relevant web pages for your query."

    # 3. Fetch HTML
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        html_dict = loop.run_until_complete(fetch_all_urls(urls))
    except RuntimeError:
        html_dict = asyncio.run(fetch_all_urls(urls))

    # 4. Clean HTML
    text_dict = {url: clean_html(html) for url, html in html_dict.items()}
    text_dict = {url: text for url, text in text_dict.items() if text}
    
    if not text_dict:
        return "I found web pages but couldn't extract readable text from them."

    # 5-7. Build Ephemeral Index
    vectorstore = build_ephemeral_index(text_dict)
    
    if not vectorstore:
        return "Could not process the text from the web pages."

    # 8. Retrieve Context
    context, sources = retrieve_context(vectorstore, clean_query, k=SIMILARITY_K)
    
    # 9-10. Generate Answer
    answer = generate_answer(clean_query, context)
    
    # 11. Source Attribution
    source_text = "\n\n**Sources:**\n" + "\n".join([f"- {s}" for s in sources])
    
    return answer + source_text
