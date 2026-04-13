"""
Level 1: Direct HTTP Probe (passive reconnaissance).

Tests what a simple HTTP client sees without a browser.
Expected result for SPA: empty HTML shell.
This level exists to DEMONSTRATE that basic scraping is blocked.
It's the baseline for the security report.

Stealth concern: minimal — just a single GET like a search engine crawler.
"""
import asyncio
import json
import time
import logging
from datetime import datetime

import aiohttp
from config import TARGETS, SITEMAP_URLS, OUTPUT_DIR, get_browser_headers
from stealth import human_delay, html_has_content

log = logging.getLogger(__name__)


async def run_level1() -> dict:
    """Send plain HTTP requests with no browser, no JS. See what comes back."""
    log.info("LEVEL 1: Direct HTTP Probe")
    log.info("   Testing: does a plain HTTP GET return tariff data?")
    start = time.time()

    results = {}
    headers = get_browser_headers()

    async with aiohttp.ClientSession(headers=headers) as session:
        # Check sitemaps
        for sitemap_url in SITEMAP_URLS:
            try:
                async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    body = await resp.text()
                    results[f"sitemap_{sitemap_url}"] = {
                        "status": resp.status,
                        "content_type": resp.headers.get("Content-Type", ""),
                        "size": len(body),
                        "accessible": resp.status == 200,
                    }
            except Exception as e:
                results[f"sitemap_{sitemap_url}"] = {"error": str(e), "accessible": False}
            await human_delay("sitemap probe")

        # Check target pages
        for name, url in TARGETS.items():
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
                    has_content = html_has_content(html)
                    results[name] = {
                        "url": url,
                        "status": resp.status,
                        "html_size": len(html),
                        "has_rendered_content": has_content,
                        "server": resp.headers.get("Server", "unknown"),
                        "cloudflare": "cloudflare" in resp.headers.get("Server", "").lower()
                                      or "cf-ray" in resp.headers,
                    }

                    html_path = OUTPUT_DIR / f"level1_{name}.html"
                    html_path.write_text(html, encoding="utf-8")

                    if has_content:
                        log.info(f"  {name}: HTTP returned content! ({len(html):,} chars)")
                    else:
                        log.info(f"  {name}: Empty SPA shell ({len(html):,} chars) — protection works")

            except Exception as e:
                results[name] = {"url": url, "error": str(e)}
                log.error(f"  {name}: {e}")

            await human_delay("http probe")

    report = {
        "level": 1,
        "method": "direct_http",
        "timestamp": datetime.now().isoformat(),
        "duration_s": time.time() - start,
        "results": results,
        "conclusion": (
            "SPA protection blocks basic HTTP scraping"
            if not any(r.get("has_rendered_content") for r in results.values() if isinstance(r, dict))
            else "WARNING: Some pages return content via plain HTTP"
        ),
    }

    path = OUTPUT_DIR / "level1_http_probe.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"  Level 1 report saved: {path}")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run_level1())
