import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse as urlparse

# Fix 3: Category-based query expansion dictionary
# Each key is a trigger term; value is a list of synonyms to append.
# The goal is to cast a wider semantic net so the retriever finds more relevant chunks.
QUERY_EXPANSIONS = {
    # Financial
    "fee":           ["application fee", "tuition fee", "cost", "payment"],
    "cost":          ["fee", "tuition", "price", "expense", "payment"],
    "tuition":       ["tuition fee", "cost", "annual fee", "semester fee"],
    "price":         ["cost", "fee", "tuition", "amount"],
    "scholarship":   ["scholarship", "financial aid", "grant", "merit aid", "funding"],
    # Deadlines — only trigger on explicit deadline words, NOT on "apply"
    "deadline":      ["application deadline", "due date", "last date", "closing date"],
    "due date":      ["deadline", "last date", "closing date"],
    # Documents / eligibility
    "document":      ["required documents", "application documents", "supporting documents",
                      "certificates", "transcripts", "checklist"],
    "eligib":        ["eligibility criteria", "minimum qualifications", "requirements",
                      "who can apply"],
    "requirements":  ["eligibility", "criteria", "qualifications", "prerequisites"],
    "how to apply":  ["application process", "admission steps", "application procedure"],
    # Rankings
    "ranking":       ["world ranking", "national ranking", "university rank", "#1", "top"],
    "rank":          ["ranking", "position", "top universities", "best colleges"],
    # Admissions process
    "admission":     ["admission process", "application", "enrollment", "requirements"],
    # Scores / Stats
    "gpa":           ["grade point average", "minimum gpa", "academic requirement"],
    "sat":           ["sat score", "standardized test", "admission test", "score requirement"],
    "act":           ["act score", "standardized test", "admission test"],
    "acceptance":    ["acceptance rate", "admit rate", "selectivity"],
}


def normalize_query(query: str) -> str:
    """
    Fix 3: Normalize and expand the user query for better retrieval.

    Strategy:
    1. Strip & lowercase for matching.
    2. Look for known trigger words and append their synonyms.
    3. De-duplicate expansion terms.
    4. Return the enriched query string for embedding.
    """
    clean = query.strip()
    lower = clean.lower()

    expansions_added = set()
    extra_terms = []

    for trigger, synonyms in QUERY_EXPANSIONS.items():
        if trigger in lower:
            for syn in synonyms:
                # Don't add terms already present in the query or already added
                if syn.lower() not in lower and syn not in expansions_added:
                    extra_terms.append(syn)
                    expansions_added.add(syn)

    if extra_terms:
        expanded = f"{clean} {' '.join(extra_terms)}"
        print(f"  [EXPAND] Query expanded: '{clean}' → '{expanded}'")
        return expanded

    return clean


def search_web(query: str, num_results: int = 5) -> List[Dict]:
    """
    Fix 4 (partial): Search the web using DuckDuckGo HTML directly.
    num_results default raised to 5 so the caller can retrieve more candidates.
    """
    print(f"  [SEARCH] Searching web for: '{query}'")
    results = []
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
        url = f"https://html.duckduckgo.com/html/?q={urlparse.quote_plus(query)}"

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            for a in soup.find_all('a', class_='result__url', limit=num_results * 3):
                href = a.get('href')
                if not href:
                    continue

                # Decode DuckDuckGo redirect links
                if href.startswith('//duckduckgo.com/l/?'):
                    parsed = urlparse.parse_qs(urlparse.urlparse(href).query)
                    href = parsed.get('uddg', [''])[0]

                # Skip ads, trackers, and DDG-internal links
                if not href or 'duckduckgo.com/' in href or 'ad_domain' in href:
                    continue

                # Avoid duplicates
                if not any(r["url"] == href for r in results):
                    results.append({"url": href})

                if len(results) >= num_results:
                    break

    except Exception as e:
        import traceback
        print(f"  [ERROR] Error during web search: {e}")
        traceback.print_exc()

    print(f"  [SEARCH] Found {len(results)} URL(s).")
    return results
