import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse as urlparse

def normalize_query(query: str) -> str:
    """Normalize and expand the user query for web search."""
    return query.strip()

def search_web(query: str, num_results: int = 3) -> List[Dict]:
    """Search the web using DuckDuckGo HTML directly."""
    print(f"  [SEARCH] Searching web for: '{query}'")
    results = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        url = f"https://html.duckduckgo.com/html/?q={query}"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for a in soup.find_all('a', class_='result__url', limit=num_results * 3):
                href = a.get('href')
                if href:
                    if href.startswith('//duckduckgo.com/l/?'):
                        parsed = urlparse.parse_qs(urlparse.urlparse(href).query)
                        href = parsed.get('uddg', [''])[0]
                    
                    # Skip ads and tracking links
                    if 'duckduckgo.com/' in href or 'ad_domain' in href:
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
        
    return results
