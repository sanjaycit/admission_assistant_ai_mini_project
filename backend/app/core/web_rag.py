import asyncio
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import GEMINI_MODEL, SIMILARITY_K
from app.services.web_search import normalize_query, search_web
from app.services.web_scraper import fetch_all_urls, clean_html
from app.services.persistent_store import search_db, add_to_db

# Fix 5: These topics need fresh web data every time — never trust the cache
VOLATILE_KEYWORDS = [
    "fee", "cost", "tuition", "price",          # Financial — change yearly
    "ranking", "rank", "rated", "best",          # Rankings — change annually
    "deadline", "due date", "closing",           # Deadlines — time-sensitive
    "latest", "current", "now", "today",         # Recency signals
    "2024", "2025", "2026", "2027",              # Year-specific data
    "scholarship", "financial aid",              # Aid packages change
]


def is_volatile_query(query: str) -> bool:
    """
    Fix 5: Determine whether the query requires fresh web data.

    Volatile queries bypass the cache entirely so stale info never reaches the LLM.
    """
    lower = query.lower()
    return any(kw in lower for kw in VOLATILE_KEYWORDS)


def generate_answer(query: str, context: str) -> str:
    """Generate final answer using Gemini via LangChain."""
    print(f"  [GENERATE] Generating answer from {len(context)} chars of context...")
    print(f"  [CONTEXT PREVIEW]\n{context[:800]}\n  [... end preview ...]")

    load_dotenv()  # loads GOOGLE_API_KEY from backend/.env
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    # Small models like gemma:2b ignore vague instructions like "use only context".
    # Instead: explicitly extract relevant fragments, then tell it to use THOSE.
    # This two-step approach (extract → answer) works much better on <7B models.
    prompt = f"""### TASK
Read the CONTEXT below and answer the QUESTION.
The context is from a trusted web source and contains the correct answer.
Do NOT say you don't have information — the answer IS in the context.
Extract numbers, dollar amounts, and figures exactly as written.

### CONTEXT
{context}

### QUESTION
{query}

### RULES
- Find and quote the specific numbers or facts that answer the question.
- If you see a table, read it row by row to find the relevant figure.
- Keep your answer to 2-3 sentences.
- Do not add caveats or disclaimers.

### ANSWER"""

    response = llm.invoke(prompt)
    return response.content


def query_web_system(query: str) -> str:
    """
    Main Web RAG pipeline with all 6 fixes applied.

    Flow:
      Query
        ↓
      Normalize + Expand (Fix 3)
        ↓
      Is query volatile? (Fix 5)
        ↓ yes → skip cache → web search
        ↓ no  → check DB
                 ↓ relevant + fresh? → answer
                 ↓ no               → web search
        ↓
      Web Search (wider net, Fix 4)
        ↓
      Fetch + Clean HTML
        ↓
      Chunk (smaller, paragraph-first, Fix 2) + Store (with timestamp, Fix 5)
        ↓
      Retrieve k=8 (Fix 4) → Rerank with keyword boost (Fix 6)
        ↓
      Answer
    """
    # Step 1 — Normalize & expand the query (Fix 3)
    clean_query = normalize_query(query)

    # Step 2 — Smart routing: bypass cache for volatile queries (Fix 5)
    cached_data = None
    if is_volatile_query(clean_query):
        print("  [ROUTER] Volatile query (fee/ranking/deadline) — bypassing cache for fresh data.")
    else:
        # Non-volatile: try the cache first
        cached_data = search_db(clean_query, threshold=1.2, k=SIMILARITY_K, require_fresh=False)

    if cached_data:
        context, sources = cached_data
        print("  [ROUTER] Cache hit — answering from persistent store.")
    else:
        # Step 3 — Web search (Fix 4: default 5 URLs → fetch more candidates)
        print("  [ROUTER] Cache miss — performing live web search.")
        search_results = search_web(clean_query, num_results=5)
        urls = [r["url"] for r in search_results if r.get("url")]

        if not urls:
            return "Sorry, I couldn't find any relevant web pages for your query."

        # Step 4 — Fetch HTML concurrently
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            html_dict = loop.run_until_complete(fetch_all_urls(urls))
        except RuntimeError:
            html_dict = asyncio.run(fetch_all_urls(urls))

        # Step 5 — Clean HTML
        text_dict = {url: clean_html(html) for url, html in html_dict.items()}
        text_dict = {url: text for url, text in text_dict.items() if text}

        if not text_dict:
            return "I found web pages but couldn't extract readable text from them."

        # Step 6 — Chunk and save to DB (Fix 2: small paragraph chunks, Fix 5: timestamps)
        add_to_db(text_dict)

        # Step 7 — Retrieve from newly populated DB
        # Slightly higher threshold since new data may be noisier
        cached_data = search_db(clean_query, threshold=1.5, k=SIMILARITY_K, require_fresh=True)

        if not cached_data:
            return "Could not retrieve relevant context from the processed web pages."

        context, sources = cached_data

    # Step 8 — Generate answer
    answer = generate_answer(clean_query, context)

    # Step 9 — Source attribution
    source_lines = "\n".join(f"- {s}" for s in sources)
    return f"{answer}\n\n**Sources:**\n{source_lines}"
