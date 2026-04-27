"""
Module for asynchronous web scraping and extracting clean text from raw HTML sources.
"""
import asyncio
import aiohttp
from typing import List, Dict, Tuple
import trafilatura

async def fetch_url(session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
    """
    Asynchronously retrieves the HTML content for a given URL.
    Returns a tuple containing the URL and the HTML string on success, or an empty string on failure.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        async with session.get(url, timeout=15, headers=headers, ssl=False) as response:
            if response.status == 200:
                html = await response.text()
                return url, html
            return url, ""
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}")
        return url, ""

async def fetch_all_urls(urls: List[str]) -> Dict[str, str]:
    """
    Executes parallel asynchronous HTTP requests across multiple URLs.
    Returns a dictionary mapping URLs to their corresponding HTML content.
    """
    print(f"  [FETCH] Fetching {len(urls)} web pages in parallel...")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return {url: html for url, html in results if html}

def clean_html(html: str) -> str:
    """
    Parses and extracts the main text content from a raw HTML string.
    Removes boilerplate elements like navigation, footers, and scripts.
    """
    if not html:
        return ""
    extracted = trafilatura.extract(html, include_links=False, include_images=False, include_comments=False)
    return extracted or ""
