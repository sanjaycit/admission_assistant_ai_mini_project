"""
Core Retrieval-Augmented Generation (RAG) pipeline router and sequence orchestration logic.
"""
import asyncio
from app.core.config import SIMILARITY_K
from app.services.web_search import search_web
from app.services.web_scraper import fetch_all_urls, clean_html
from app.services.persistent_store import search_db, add_to_db

from app.core.entity_extractor import extract_query_entities
from app.services.llm_service import analyze_query, generate_answer




def is_query_context_aligned(query: str, context: str) -> bool:
    """
    Validates if the cached context actually aligns with the query's intent.
    Prevents returning 'ranking' data when the user asked for 'cutoff'.
    """
    q_lower = query.lower()
    c_lower = context.lower()

    # Core data points
    if "cutoff" in q_lower and "cutoff" not in c_lower:
        return False
    if "ranking" in q_lower and "rank" not in c_lower:
        return False
    if "fees" in q_lower and "fee" not in c_lower:
        return False

    # Admission Guidance (Eligibility, Documents, Deadlines, Process)
    if any(w in q_lower for w in ["eligibility", "eligible"]) and not any(w in c_lower for w in ["eligibility", "eligible", "criteria"]):
        return False
    
    if any(w in q_lower for w in ["document", "certificate"]) and not any(w in c_lower for w in ["document", "certificate"]):
        return False
        
    if any(w in q_lower for w in ["deadline", "last date"]) and not any(w in c_lower for w in ["deadline", "date", "schedule"]):
        return False
        
    if any(w in q_lower for w in ["process", "checklist", "step", "how to apply"]) and not any(w in c_lower for w in ["process", "step", "apply", "procedure", "checklist"]):
        return False

    return True


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
        if not is_query_context_aligned(clean_query, ctx):
            print(f"  [ROUTER][{label}] Context mismatch → going to web")
            cached = None
        else:
            print(f"  [ROUTER][{label}] Cache hit — using stored data.")
            return ctx, srcs

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
    """
    # Step 1 — Detect query type
    entities = extract_query_entities(query)
    
    # Step 2 — Analyze & expand the query via LLM
    clean_query, is_comparison, admission_guidance_type = analyze_query(query)
    
    # Fallback to rule-based if LLM didn't detect comparison but we have 2+ entities and keywords
    if not is_comparison and len(entities) >= 2 and any(t in query.lower() for t in ["compare", "vs", "versus", "difference"]):
        is_comparison = True

    if is_comparison:
        print(f"  [ROUTER] Comparison query detected. Entities: {entities}")
    elif admission_guidance_type:
        print(f"  [ROUTER] Admission guidance query detected — type: '{admission_guidance_type}'.")
    elif entities:
        print(f"  [ENTITY] Detected college entity: '{entities[0]}'")
    else:
        print("  [ENTITY] No specific college detected — searching without entity filter.")

    # Comparison path: resolve context for each entity and merge results
    if is_comparison:
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

        # Format sources with [1], [2] for inline citation matching
        sources = list(dict.fromkeys(all_sources))
        
        # Inject source indexes into context so the LLM can cite them
        context_with_sources = "SOURCES LIST:\n"
        for i, src in enumerate(sources, 1):
            context_with_sources += f"[{i}] {src}\n"
        context_with_sources += "\nCONTEXT DATA:\n" + "\n\n".join(merged_context_parts)
        
        answer = generate_answer(clean_query, context_with_sources, is_comparison=True, admission_guidance_type=None)
        src_text = "\n".join(f"[{i}] {s}" for i, s in enumerate(sources, 1))
        return f"{answer}\n\n**Sources:**\n{src_text}"

    # Single-entity path
    entity = entities[0] if entities else None
    result = _resolve_entity_context(entity, clean_query)

    if not result:
        return "Could not retrieve relevant context from the processed web pages."

    context, sources = result
    
    # Inject source indexes into context so the LLM can cite them
    context_with_sources = "SOURCES LIST:\n"
    for i, src in enumerate(sources, 1):
        context_with_sources += f"[{i}] {src}\n"
    context_with_sources += "\nCONTEXT DATA:\n" + context
    
    answer = generate_answer(clean_query, context_with_sources, is_comparison=False, admission_guidance_type=admission_guidance_type)
    src_text = "\n".join(f"[{i}] {s}" for i, s in enumerate(sources, 1))
    return f"{answer}\n\n**Sources:**\n{src_text}"
