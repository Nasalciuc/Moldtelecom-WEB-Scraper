"""
Sitemap Analyzer — discover all URLs Moldtelecom exposes.

Strategy:
1. Fetch sitemap.xml via aiohttp with browser headers
2. If HTTP error, retry via Pydoll browser (handles JS-protected sitemaps)
3. Parse XML with xml.etree.ElementTree; fallback to regex on parse failure
4. Categorize discovered URLs by content type
5. Save output/sitemap_analysis.json
"""
import asyncio
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import aiohttp

from config import (
    BROWSER_HEADERS, OUTPUT_DIR, SITEMAP_URLS,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, PAGE_LOAD_WAIT,
)

log = logging.getLogger(__name__)

SITEMAP_OUTPUT = OUTPUT_DIR / "sitemap_analysis.json"

# URL categorization patterns (case-insensitive)
_CATEGORIES: list[tuple[str, re.Pattern]] = [
    ("mobile_subscriptions", re.compile(r"abonament.*mobil|telefonie.*mobil|liberty|star", re.I)),
    ("mobile_options",       re.compile(r"optiuni.*mobil|roaming|prepay|portare", re.I)),
    ("internet",             re.compile(r"internet|fibra|wi-fi|WiFi", re.I)),
    ("tv",                   re.compile(r"/tv|televiziune|canale", re.I)),
    ("phones",               re.compile(r"phone|telefon|samsung|iphone|xiaomi", re.I)),
    ("business",             re.compile(r"business", re.I)),
]

_RE_URL_FALLBACK = re.compile(r"https?://[^\s<\"']+moldtelecom[^\s<\"']*", re.I)


def _categorize(url: str) -> str:
    for category, pattern in _CATEGORIES:
        if pattern.search(url):
            return category
    return "other"


def _parse_xml_sitemap(text: str) -> list[str]:
    """Extract <loc> URLs from sitemap XML. Returns empty list on failure."""
    try:
        root = ET.fromstring(text)
        # Namespace-aware search
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [el.text.strip() for el in root.findall(".//sm:loc", ns) if el.text]
        if not urls:
            # Try without namespace
            urls = [el.text.strip() for el in root.findall(".//loc") if el.text]
        return urls
    except ET.ParseError as e:
        log.warning(f"  ⚠️ XML parse error: {e}")
        return []


def _regex_extract_urls(text: str) -> list[str]:
    """Fallback: regex-extract all moldtelecom.md URLs from arbitrary text."""
    return list(dict.fromkeys(_RE_URL_FALLBACK.findall(text)))  # deduplicate, preserve order


async def _fetch_via_aiohttp(url: str) -> tuple[int, str]:
    """Return (status_code, body_text). status=0 on connection error."""
    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(connect=10, sock_read=20)
    try:
        async with aiohttp.ClientSession(
            headers=BROWSER_HEADERS, connector=connector
        ) as session:
            async with session.get(url, timeout=timeout) as resp:
                text = await resp.text(encoding="utf-8", errors="replace")
                return resp.status, text
    except Exception as e:
        log.warning(f"  aiohttp error for {url}: {e}")
        return 0, ""


async def _fetch_via_pydoll(url: str) -> str:
    """Fallback: use Pydoll browser to fetch sitemap (handles JS challenges)."""
    try:
        from pydoll.browser.chromium import Chrome
        from pydoll.browser.options import ChromiumOptions
    except ImportError:
        log.error("pydoll-python not installed — cannot use browser fallback")
        return ""

    options = ChromiumOptions()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")

    try:
        async with Chrome(options=options) as browser:
            tab = await browser.start()
            await tab.go_to(url)
            await asyncio.sleep(PAGE_LOAD_WAIT)
            content = await tab.page_source
            return content or ""
    except Exception as e:
        log.error(f"  Pydoll fetch failed for {url}: {e}")
        return ""


async def _process_sitemap_url(url: str) -> tuple[list[str], str]:
    """
    Try to fetch and parse a sitemap URL.
    Returns (list_of_urls_found, method_used).
    """
    log.info(f"  📡 Fetching sitemap: {url}")
    status, body = await _fetch_via_aiohttp(url)

    if status == 200 and body:
        urls = _parse_xml_sitemap(body)
        if urls:
            return urls, "aiohttp+xml"
        # XML parse failed — try regex
        urls = _regex_extract_urls(body)
        if urls:
            return urls, "aiohttp+regex"

    # HTTP failed or empty — try browser
    log.info(f"  🌐 Falling back to Pydoll browser for {url}")
    body = await _fetch_via_pydoll(url)
    if body:
        urls = _parse_xml_sitemap(body)
        if urls:
            return urls, "pydoll+xml"
        urls = _regex_extract_urls(body)
        if urls:
            return urls, "pydoll+regex"

    return [], "failed"


async def analyze_sitemap() -> dict:
    """
    Main entry point: analyze all sitemap URLs and categorize them.
    Returns structured dict and saves output/sitemap_analysis.json.
    """
    log.info("📡 Starting sitemap analysis...")
    start = time.time()

    all_urls: list[str] = []
    sitemap_meta: list[dict] = []

    for sitemap_url in SITEMAP_URLS:
        found, method = await _process_sitemap_url(sitemap_url)
        log.info(f"  → {len(found)} URL(s) via {method}")
        sitemap_meta.append({
            "sitemap_url": sitemap_url,
            "urls_found": len(found),
            "method": method,
        })
        all_urls.extend(found)

        await asyncio.sleep(REQUEST_DELAY_MIN)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    # Categorize
    categorized: dict[str, list[str]] = {
        cat: [] for cat, _ in _CATEGORIES
    }
    categorized["other"] = []

    for url in unique_urls:
        cat = _categorize(url)
        categorized[cat].append(url)

    # Summary counts
    category_counts = {cat: len(urls) for cat, urls in categorized.items()}
    log.info(f"  📊 Category breakdown: {category_counts}")

    output = {
        "analysis_date": datetime.now().isoformat(),
        "sitemaps_checked": sitemap_meta,
        "total_urls_discovered": len(unique_urls),
        "category_counts": category_counts,
        "urls_by_category": categorized,
        "duration_seconds": round(time.time() - start, 2),
    }

    SITEMAP_OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(
        f"  💾 Sitemap analysis saved: {SITEMAP_OUTPUT} "
        f"({len(unique_urls)} URLs total)"
    )

    return output


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    asyncio.run(analyze_sitemap())
