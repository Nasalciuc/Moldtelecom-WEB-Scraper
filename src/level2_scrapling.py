"""
Level 2: Scrapling StealthyFetcher — PRIMARY scraping method.

StealthyFetcher capabilities:
- Bypasses Cloudflare Turnstile / JS challenges
- Spoofs browser fingerprints (canvas, WebGL, fonts)
- Full JavaScript rendering
- Adaptive selectors that survive website redesigns

STEALTH APPROACH:
1. Visit homepage first (warmup — look like a real user)
2. Wait 3-7 seconds (human reading time)
3. Navigate to tariff page (like clicking a menu link)
4. Scroll slowly through page (triggers lazy loading)
5. Extract data
6. Wait before next page
"""
import asyncio
import json
import time
import logging
import random
from datetime import datetime

from config import TARGETS, OUTPUT_DIR, WARMUP_URL, DELAY_SESSION_WARMUP
from stealth import human_delay, page_delay, html_has_content

log = logging.getLogger(__name__)


def _scrapling_available() -> bool:
    try:
        from scrapling.fetchers import StealthyFetcher
        return True
    except ImportError:
        return False


async def run_level2() -> dict:
    """Fetch all target pages with Scrapling StealthyFetcher. Mimics real user browsing."""
    if not _scrapling_available():
        log.warning("Scrapling not installed — skipping Level 2")
        return {"level": 2, "available": False, "error": "scrapling not installed"}

    from scrapling.fetchers import StealthyFetcher

    log.info("LEVEL 2: Scrapling StealthyFetcher")
    start = time.time()
    results = {}

    # Step 1: Warmup — visit homepage first (look like a real user)
    log.info("  Warmup: visiting homepage first...")
    try:
        homepage = StealthyFetcher.fetch(WARMUP_URL, headless=True, network_idle=True)
        log.info(f"  Homepage loaded ({len(str(homepage)):,} chars)")
        await asyncio.sleep(DELAY_SESSION_WARMUP + random.uniform(0, 3))
    except Exception as e:
        log.warning(f"  Homepage warmup failed: {e} — continuing anyway")
        await asyncio.sleep(2)

    # Step 2: Visit target pages one by one
    for name, url in TARGETS.items():
        log.info(f"\n  Target: {name}")
        result = {
            "url": url,
            "success": False,
            "html_size": 0,
            "has_content": False,
            "stealth_bypass": False,
            "elements_found": 0,
            "error": "",
        }

        try:
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

            # If we got here — anti-bot was bypassed (or absent)
            result["stealth_bypass"] = True

            html = page.html_content if hasattr(page, "html_content") else str(page)
            result["html_size"] = len(html)
            result["has_content"] = html_has_content(html)

            if result["has_content"]:
                log.info(f"  Content loaded: {len(html):,} chars")

                # Save rendered HTML
                html_path = OUTPUT_DIR / f"level2_{name}.html"
                html_path.write_text(html, encoding="utf-8")

                # Try to find tariff-related elements
                selectors_to_try = [
                    "[class*='tariff']", "[class*='plan']", "[class*='price']",
                    "[class*='abonament']", "[class*='card']", "[class*='offer']",
                    ".tariff", ".plan", ".price-card", ".subscription",
                ]
                for sel in selectors_to_try:
                    try:
                        elements = page.css(sel)
                        if elements and len(elements) > 0:
                            result["elements_found"] += len(elements)
                            log.info(f"    '{sel}' -> {len(elements)} elements")
                    except Exception:
                        continue

                result["success"] = True
            else:
                log.warning(f"  Page loaded but content seems empty ({len(html)} chars)")

        except Exception as e:
            result["error"] = str(e)
            log.error(f"  Scrapling failed for {name}: {e}")

        results[name] = result
        await page_delay(f"after {name}")

    report = {
        "level": 2,
        "method": "scrapling_stealthy",
        "timestamp": datetime.now().isoformat(),
        "duration_s": time.time() - start,
        "available": True,
        "pages_fetched": len(results),
        "pages_with_content": sum(1 for r in results.values() if r.get("has_content")),
        "anti_bot_bypassed": sum(1 for r in results.values() if r.get("stealth_bypass")),
        "results": results,
    }

    path = OUTPUT_DIR / "level2_scrapling_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"\n  Level 2 report saved: {path}")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run_level2())
