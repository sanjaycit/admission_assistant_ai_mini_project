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

# Topic → what concrete signals must appear in context to call it "sufficient"
# If a query is about fees but no chunk contains "$" or a number, the cache is useless
SUFFICIENCY_SIGNALS = {
    "fee":        ["$", "usd", "inr", "rs.", "lakh", "₹", "tuition", "cost", "per year"],
    "cost":       ["$", "usd", "inr", "rs.", "lakh", "₹", "fee", "total", "per year"],
    "tuition":    ["$", "usd", "inr", "rs.", "lakh", "₹", "per year", "semester"],
    "ranking":    ["#", "rank", "ranked", "position", "top", "world ranking", "qs"],
    "deadline":   ["deadline", "january", "february", "march", "april", "may",
                   "june", "july", "august", "september", "october", "november", "december"],
    "gpa":        ["gpa", "grade point", "minimum", "average", "3.", "4."],
    "sat":        ["sat", "score", "1", "percentile"],
    "acceptance": ["rate", "%", "percent", "accepted", "applicants"],
}


def is_volatile_query(query: str) -> bool:
    """
    Fix 5: Determine whether the query requires fresh web data.
    Volatile queries bypass the cache entirely so stale info never reaches the LLM.
    """
    lower = query.lower()
    return any(kw in lower for kw in VOLATILE_KEYWORDS)


def extract_query_entities(query: str) -> list[str]:
    """
    Extract ALL college/institution names from the query.

    Unlike the old single-entity version, this returns a list so comparison
    queries like 'Compare MIT and SSN' yield ['mit', 'ssn'].

    Strategy (applied in order, results accumulated):
      1. ALL-CAPS acronyms 2+ chars  →  SSN, MIT, IIT, NIT, BITS, VIT
      2. Word(s) before University/College/Institute
         e.g. 'Stanford University' → 'stanford'
      3. Remaining capitalized words not in stop list
    """
    import re

    STOP_WORDS = {
        "what", "how", "much", "is", "the", "for", "of", "at", "in", "a", "an",
        "and", "or", "vs", "versus", "between", "compare", "both",
        "admission", "fee", "cost", "tuition", "ranking", "deadline",
        "university", "college", "institute", "school",
    }

    found = []  # preserves insertion order, no duplicates

    # 1. ALL-CAPS acronyms: SSN, MIT, IIT, etc.
    for acr in re.findall(r'\b[A-Z]{2,}\b', query):
        key = acr.lower()
        if key not in STOP_WORDS and key not in found:
            found.append(key)

    # 2. Name(s) directly before University / College / Institute / School
    for m in re.finditer(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:University|College|Institute|School)\b',
        query,
    ):
        key = m.group(1).lower()
        if key not in STOP_WORDS and key not in found:
            found.append(key)

    # 3. Any remaining capitalized proper nouns
    for w in re.findall(r'\b[A-Z][a-z]{2,}\b', query):
        key = w.lower()
        if key not in STOP_WORDS and key not in found:
            found.append(key)

    return found


def extract_query_entity(query: str) -> str | None:
    """Convenience wrapper — returns the first entity or None (single-entity queries)."""
    entities = extract_query_entities(query)
    return entities[0] if entities else None


def is_comparison_query(query: str) -> bool:
    """Detect if the user is asking to compare two or more colleges."""
    lower = query.lower()
    COMPARE_TRIGGERS = ["compare", "vs", "versus", "difference between",
                        "better", "which is", "both", "and"]
    has_trigger = any(t in lower for t in COMPARE_TRIGGERS)
    # Only treat as comparison if 2+ entities are found
    return has_trigger and len(extract_query_entities(query)) >= 2


def is_context_sufficient(query: str, context: str) -> bool:
    """
    Gate 1 — Entity match: the context must be about the SAME college as the query.
    Gate 2 — Factual signals: the context must contain concrete numbers/dates.

    Both gates must pass for the cache to be used.
    """
    lower_query   = query.lower()
    lower_context = context.lower()

    # ── Gate 1: Entity match ─────────────────────────────────────────────────
    entity = extract_query_entity(query)
    if entity:
        if entity not in lower_context:
            print(f"  [ENTITY] Query is about '{entity}' but context doesn't mention it.")
            print(f"  [ENTITY] Context is about a DIFFERENT college — going to web.")
            return False
        else:
            print(f"  [ENTITY] Entity '{entity}' confirmed in context. ✓")

    # ── Gate 2: Factual signals ──────────────────────────────────────────────
    matched_topics = [topic for topic in SUFFICIENCY_SIGNALS if topic in lower_query]

    if not matched_topics:
        # No specific topic detected → entity match alone is enough
        return True

    for topic in matched_topics:
        signals = SUFFICIENCY_SIGNALS[topic]
        if any(sig in lower_context for sig in signals):
            print(f"  [SUFFICIENCY] Topic '{topic}' — concrete signals found. Cache is sufficient.")
            return True

    print(f"  [SUFFICIENCY] Topics {matched_topics} found in query but NO concrete signals in context.")
    print("  [SUFFICIENCY] Cache is insufficient → going to web for fresh data.")
    return False


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


def _resolve_entity_context(
    entity: str,
    clean_query: str,
) -> tuple[str, list[str]] | None:
    """
    For a single entity: check cache, fall back to web, return (context, sources).
    Used by both single-college and comparison flows.
    """
    # Cache lookup (entity-filtered + fresh)
    cached = search_db(clean_query, entity=entity, threshold=1.2,
                       k=SIMILARITY_K, require_fresh=True)

    if cached:
        ctx, srcs = cached
        if is_context_sufficient(clean_query, ctx):
            print(f"  [ROUTER][{entity.upper()}] Cache hit — using stored data.")
            return ctx, srcs
        else:
            print(f"  [ROUTER][{entity.upper()}] Cache insufficient — going to web.")
            cached = None

    if not cached:
        print(f"  [ROUTER][{entity.upper()}] Fetching from web...")
        # Build a targeted search query: entity name + original intent
        targeted_query = f"{entity} {clean_query}"
        results = search_web(targeted_query, num_results=5)
        urls = [r["url"] for r in results if r.get("url")]

        if not urls:
            print(f"  [ROUTER][{entity.upper()}] No URLs found.")
            return None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            html_dict = loop.run_until_complete(fetch_all_urls(urls))
        except RuntimeError:
            html_dict = asyncio.run(fetch_all_urls(urls))

        text_dict = {url: clean_html(html) for url, html in html_dict.items()}
        text_dict = {url: t for url, t in text_dict.items() if t}

        if not text_dict:
            return None

        add_to_db(text_dict, entity=entity)

        cached = search_db(clean_query, entity=entity, threshold=1.5,
                           k=SIMILARITY_K, require_fresh=True)

        if not cached:
            return None

    return cached


def query_web_system(query: str) -> str:
    """
    Entity-aware + Comparison-aware Web RAG pipeline.

    Single-entity:   fetch context for that college only.
    Multi-entity:    fetch context for EACH college independently,
                     merge into one context, then compare.
    """
    # Step 1 — Detect query type
    entities = extract_query_entities(query)
    comparison = is_comparison_query(query)

    if comparison:
        print(f"  [ROUTER] Comparison query detected. Entities: {entities}")
    elif entities:
        print(f"  [ENTITY] Detected college entity: '{entities[0]}'")
    else:
        print("  [ENTITY] No specific college detected — searching without entity filter.")

    # Step 2 — Normalize & expand the query
    clean_query = normalize_query(query)

    # ────────────────────────────────────────────────────────────
    # Comparison path: resolve context for EACH entity, merge
    # ────────────────────────────────────────────────────────────
    if comparison:
        merged_context_parts = []
        all_sources = []

        for ent in entities:
            result = _resolve_entity_context(ent, clean_query)
            if result:
                ctx, srcs = result
                merged_context_parts.append(f"### {ent.upper()} ###\n{ctx}")
                all_sources.extend(srcs)
            else:
                merged_context_parts.append(
                    f"### {ent.upper()} ###\nNo information found for {ent.upper()}."
                )

        if not any("No information" not in p for p in merged_context_parts):
            return "Could not find information for any of the requested colleges."

        context  = "\n\n" + "\n\n".join(merged_context_parts)
        sources  = list(dict.fromkeys(all_sources))  # deduplicated, order preserved
        answer   = generate_answer(clean_query, context)
        src_text = "\n".join(f"- {s}" for s in sources)
        return f"{answer}\n\n**Sources:**\n{src_text}"

    # ────────────────────────────────────────────────────────────
    # Single-entity path (original flow)
    # ────────────────────────────────────────────────────────────
    entity = entities[0] if entities else None
    result = _resolve_entity_context(entity, clean_query)

    if not result:
        return "Could not retrieve relevant context from the processed web pages."

    context, sources = result
    answer = generate_answer(clean_query, context)
    src_text = "\n".join(f"- {s}" for s in sources)
    return f"{answer}\n\n**Sources:**\n{src_text}"
