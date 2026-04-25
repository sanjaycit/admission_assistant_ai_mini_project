import asyncio
from langchain_ollama import ChatOllama
from app.core.config import LLM_MODEL, SIMILARITY_K
from app.services.web_search import normalize_query, search_web
from app.services.web_scraper import fetch_all_urls, clean_html
from app.services.persistent_store import search_db, add_to_db

def is_volatile_query(query: str) -> bool:
    """Check if the query asks for frequently changing data."""
    clean = query.lower()
    volatile_keywords = ["fee", "cost", "tuition", "price", "ranking", "deadline", "latest", "now", "current", "2024", "2025", "2026"]
    return any(kw in clean for kw in volatile_keywords)

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
    """Main pipeline for Web RAG with Semantic Caching."""
    # 1. Normalize Query
    clean_query = normalize_query(query)
    
    # 2. Smart Routing & Cache Bypassing
    cached_data = None
    if is_volatile_query(clean_query):
        print("  [ROUTER] Volatile query detected. Bypassing cache to ensure freshness.")
    else:
        # Check Persistent DB Cache
        cached_data = search_db(clean_query, threshold=1.2, k=SIMILARITY_K)
    
    if cached_data:
        # We found highly relevant data in the DB!
        context, sources = cached_data
    else:
        # 3. Search Web (Cache Miss)
        search_results = search_web(clean_query, num_results=5)
        urls = [r["url"] for r in search_results if r["url"]]
        
        if not urls:
            return "Sorry, I couldn't find any relevant web pages for your query."

        # 4. Fetch HTML
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            html_dict = loop.run_until_complete(fetch_all_urls(urls))
        except RuntimeError:
            html_dict = asyncio.run(fetch_all_urls(urls))

        # 5. Clean HTML
        text_dict = {url: clean_html(html) for url, html in html_dict.items()}
        text_dict = {url: text for url, text in text_dict.items() if text}
        
        if not text_dict:
            return "I found web pages but couldn't extract readable text from them."

        # 6. Save to Persistent DB
        add_to_db(text_dict)
        
        # 7. Retrieve Context from newly populated DB
        cached_data = search_db(clean_query, threshold=1.5, k=SIMILARITY_K) # Slightly higher threshold just in case
        
        if not cached_data:
            return "Could not retrieve relevant context from the processed web pages."
            
        context, sources = cached_data

    # 8. Generate Answer
    answer = generate_answer(clean_query, context)
    
    # 9. Source Attribution
    source_text = "\n\n**Sources:**\n" + "\n".join([f"- {s}" for s in sources])
    
    return answer + source_text
