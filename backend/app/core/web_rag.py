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

# ---------------------------------------------------------------------------
# Alias map — fused abbreviations → canonical compound entity key
# Used by extract_query_entities to normalise user shorthand BEFORE regex.
# Keys are lowercase; values are the canonical form stored in the cache.
# ---------------------------------------------------------------------------
COLLEGE_ALIASES: dict[str, str] = {
    # IIT campuses
    "iitb":    "iit bombay",
    "iitm":    "iit madras",
    "iitd":    "iit delhi",
    "iitk":    "iit kanpur",
    "iitkgp":  "iit kharagpur",
    "iitg":    "iit guwahati",
    "iitr":    "iit roorkee",
    "iith":    "iit hyderabad",
    "iiti":    "iit indore",
    "iitbbs":  "iit bhubaneswar",
    "iitbhu":  "iit bhu",
    "iitmandi":"iit mandi",
    # NIT campuses
    "nitk":    "nit karnataka",
    "nitt":    "nit trichy",
    "nitr":    "nit rourkela",
    "nitp":    "nit patna",
    "nitw":    "nit warangal",
    "nitc":    "nit calicut",
    # Other common colleges
    "vitc":    "vit chennai",
    "vitv":    "vit vellore",
    "srmktr":  "srm kattankulathur",
    "bitsphd": "bits pilani",
    "bitsh":   "bits hyderabad",
    "bitsg":   "bits goa",
}


def resolve_aliases(query_lower: str) -> tuple[list[str], set[str]]:
    """
    Scan every whitespace-separated token in the lowercased query against
    COLLEGE_ALIASES.  Returns:
      - found:    canonical entity keys resolved from aliases
      - consumed: original tokens that were matched (so regex steps skip them)
    """
    found: list[str] = []
    consumed: set[str] = set()
    for token in query_lower.split():
        canonical = COLLEGE_ALIASES.get(token)
        if canonical and canonical not in found:
            found.append(canonical)
            consumed.add(token)
            # Also consume the individual words of the canonical form so
            # they don't get re-added as separate entities later.
            consumed.update(canonical.split())
    return found, consumed


def is_volatile_query(query: str) -> bool:
    """
    Determine whether the query requires fresh web data.
    Volatile queries bypass the cache entirely so stale info never reaches the LLM.
    """
    lower = query.lower()
    return any(kw in lower for kw in VOLATILE_KEYWORDS)


def extract_query_entities(query: str) -> list[str]:
    """
    Extract ALL college/institution names from the query as compound entities.

    Strategy (applied in order):
      0. Compound ACRONYM + qualifier  →  'IIT Bombay' → 'iit bombay',
                                          'NIT Trichy'  → 'nit trichy'
         These are detected FIRST so that standalone acronym scan doesn't
         split 'IIT Bombay' into separate 'iit' and 'bombay' entries.
      1. Remaining standalone ALL-CAPS acronyms not consumed by step 0
      2. Word(s) before University/College/Institute  → 'stanford'
      3. Remaining capitalized proper nouns not consumed by step 0
    """
    import re

    STOP_WORDS = {
        "what", "how", "much", "is", "the", "for", "of", "at", "in", "a", "an",
        "and", "or", "vs", "versus", "between", "compare", "both",
        "admission", "fee", "cost", "tuition", "ranking", "deadline",
        "university", "college", "institute", "school",
    }

    # ── Step -1: alias resolution (case-insensitive, handles 'iitb', 'IITB', etc.) ──
    found, consumed = resolve_aliases(query.lower())

    # ── Step 0: Compound ACRONYM + Title-case qualifier in ORIGINAL query ────
    #    Handles mixed-case input like 'IIT Bombay' that aliases don't cover.
    #    Matches: "IIT Bombay", "IIT Madras", "NIT Trichy", "BITS Pilani"
    #    Qualifier must NOT be a stop word (filters out "IIT College" etc.)
    for m in re.finditer(r'\b([A-Z]{2,})\s+([A-Z][a-z]{2,})\b', query):
        acronym, qualifier = m.group(1), m.group(2)
        acr_key, q_key = acronym.lower(), qualifier.lower()
        if q_key not in STOP_WORDS:
            key = f"{acr_key} {q_key}"   # e.g. 'iit bombay'
            if key not in found:
                found.append(key)
            consumed.add(acr_key)
            consumed.add(q_key)

    # ── Step 1: Standalone ALL-CAPS acronyms not already consumed ────────────
    for acr in re.findall(r'\b[A-Z]{2,}\b', query):
        key = acr.lower()
        if key not in STOP_WORDS and key not in found and key not in consumed:
            found.append(key)

    # 2. Name(s) directly before University / College / Institute / School
    for m in re.finditer(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:University|College|Institute|School)\b',
        query,
    ):
        key = m.group(1).lower()
        if key not in STOP_WORDS and key not in found:
            found.append(key)

    # 3. Remaining capitalized proper nouns not consumed by step 0
    for w in re.findall(r'\b[A-Z][a-z]{2,}\b', query):
        key = w.lower()
        if key not in STOP_WORDS and key not in found and key not in consumed:
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



# Keywords that indicate the user wants a structured process/checklist answer
CHECKLIST_KEYWORDS = [
    "eligib", "document", "required", "checklist", "steps", "how to apply",
    "process", "procedure", "what do i need", "criteria",
    "requirement", "deadline", "when to apply", "admission process",
]


def _is_checklist_query(query: str) -> bool:
    """Detect whether the user wants a step-by-step / structured answer."""
    lower = query.lower()
    return any(kw in lower for kw in CHECKLIST_KEYWORDS)


def generate_answer(query: str, context: str) -> str:
    """Generate final answer using Gemini via LangChain.

    Intent-aware: produces structured markdown (headings, checkboxes, numbered
    steps) for process/eligibility/document queries, and concise 2-3 sentence
    answers for factual queries (fees, rankings, etc.).
    """
    print(f"  [GENERATE] Generating answer from {len(context)} chars of context...")
    print(f"  [CONTEXT PREVIEW]\n{context[:800]}\n  [... end preview ...]")

    load_dotenv()
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    if _is_checklist_query(query):
        prompt = f"""### TASK
Read the CONTEXT below and answer the QUESTION with a well-structured guide.
Use only information present in the context.

### CONTEXT
{context}

### QUESTION
{query}

### RULES
Structure your answer using only the relevant sections below:

## Eligibility Criteria
(bullet list of minimum qualifications)

## Required Documents
- [ ] Document 1
- [ ] Document 2
(use "- [ ]" prefix for every document so the user can check them off)

## Key Deadlines
(bullet list of important dates with labels)

## Steps to Apply
1. Step one
2. Step two
(numbered, action-oriented steps in order)

## Additional Notes
(any important tips or warnings — optional)

- Use **bold** for important terms.
- Omit any section the context has no data for.
- Do NOT add caveats or say you don't know.

### ANSWER"""
    else:
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
    entity: str | None,
    clean_query: str,
) -> tuple[str, list[str]] | None:
    """
    For a single entity: check cache, fall back to web, return (context, sources).
    Used by both single-college and comparison flows.
    """
    # Cache lookup (entity-filtered + fresh)
    cached = search_db(clean_query, entity=entity, threshold=1.2,
                       k=SIMILARITY_K, require_fresh=True)

    label = entity.upper() if entity else "UNKNOWN"

    if cached:
        ctx, srcs = cached
        if is_context_sufficient(clean_query, ctx):
            print(f"  [ROUTER][{label}] Cache hit — using stored data.")
            return ctx, srcs
        else:
            print(f"  [ROUTER][{label}] Cache insufficient — going to web.")
            cached = None

    if not cached:
        print(f"  [ROUTER][{label}] Fetching from web...")
        # Prefix the search with the entity name when known; if entity is None
        # (user typed an unknown name in lowercase) just use the raw query —
        # it already contains enough signal for the search engine.
        targeted_query = f"{entity} {clean_query}" if entity else clean_query
        results = search_web(targeted_query, num_results=5)
        urls = [r["url"] for r in results if r.get("url")]

        if not urls:
            print(f"  [ROUTER][{label}] No URLs found.")
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
