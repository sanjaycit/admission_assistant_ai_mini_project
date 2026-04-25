# scraper.py - Web scraping and content extraction functions

import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.core.config import HEADERS, MAX_RETRIES, TIMEOUT

def fetch_url(url):
    """Fetch URL content with retries"""
    for _ in range(MAX_RETRIES):
        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code == 200:
                return res.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            time.sleep(1)
    return None

def get_sitemap_links(base_url):
    """Extract links from sitemap.xml"""
    sitemap_url = base_url.rstrip("/") + "/page-sitemap.xml"
    print(sitemap_url)
    content = fetch_url(sitemap_url)

    links = []
    if content:
        try:
            root = ET.fromstring(content)
            for url in root.findall(".//{*}loc"):
                links.append(url.text)
        except Exception as e:
            print(f"Warning: Error parsing sitemap for {base_url} (falling back to homepage crawl): {e}")

    return links

def crawl_homepage(base_url):
    """Crawl homepage and extract all links"""
    html = fetch_url(base_url)
    links = set()

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            links.add(urljoin(base_url, a['href']))

    return list(links)

def filter_admission_links(links):
    """Filter links to only admission-related pages and exclude media files"""
    keywords = ["admission", "admissions", "apply", "ug-admission", "pg-admission"]
    ignore_exts = [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".mp4", ".zip", ".rar"]
    
    valid_links = []
    for l in links:
        l_lower = l.lower()
        if any(k in l_lower for k in keywords):
            from urllib.parse import urlparse
            path = urlparse(l_lower).path
            if not any(path.endswith(ext) for ext in ignore_exts):
                valid_links.append(l)
                
    return valid_links

def scrape_page(url):
    """Scrape and clean text content from a webpage"""
    html = fetch_url(url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts, styles, and other non-content elements
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Get text content
    text = soup.get_text(separator=" ", strip=True)

    # Clean up extra whitespace
    import re
    text = re.sub(r'\s+', ' ', text).strip()

    return text