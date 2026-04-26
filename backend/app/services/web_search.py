from typing import List, Dict

# normalize_query has been moved to web_rag.py and uses an LLM


def search_web(query: str, intent: str = "vague", num_results: int = 5) -> List[Dict]:
    """
    Search the web using ddgs (DuckDuckGo).
    """
    search_query = query
    # Note: DuckDuckGo's API tends to fail or return 0 results when complex OR site filters are used.
    # We rely on the LLM's query rewriting to have formulated a good query instead.
        
    print(f"  [SEARCH] Searching web for: '{search_query}' (intent: {intent})")
    results = []
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(search_query, max_results=num_results):
                href = r.get("href")
                if href and not any(res["url"] == href for res in results):
                    results.append({"url": href})
                    if len(results) >= num_results:
                        break
    except Exception as e:
        import traceback
        print(f"  [ERROR] Error during web search: {e}")
        traceback.print_exc()

    print(f"  [SEARCH] Found {len(results)} URL(s).")
    return results
