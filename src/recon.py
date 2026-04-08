"""
Reconnaissance module — stealth browser + network interception.

Uses Pydoll (CDP-based, no webdriver flag) to:
1. Open Moldtelecom pages like a real browser
2. Intercept ALL network requests/responses
3. Discover API endpoints that the SPA calls
4. Save fully rendered HTML (after JS execution)
"""
import asyncio
import json
import time
import logging
import random
from datetime import datetime

from config import (
    TARGETS, OUTPUT_DIR, SUBSCRIPTION_KEYWORDS,
    PAGE_LOAD_WAIT, SCROLL_STEPS, SCROLL_DELAY,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
)
from models import ReconResult, DiscoveredEndpoint

log = logging.getLogger(__name__)


class NetworkCapture:
    """Captures and categorizes all browser network traffic."""

    def __init__(self):
        self.requests: list[dict] = []
        self.json_responses: list[dict] = []
        self.discovered_apis: list[DiscoveredEndpoint] = []
        self._response_bodies: dict[str, str] = {}  # request_id -> body

    def handle_request(self, event: dict):
        """CDP Network.requestWillBeSent callback."""
        params = event.get("params", {})
        req = params.get("request", {})
        url = req.get("url", "")
        method = req.get("method", "GET")

        # Skip static assets
        skip_extensions = (
            ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".css", ".woff", ".woff2", ".ttf", ".ico",
        )
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return

        self.requests.append({
            "url": url,
            "method": method,
            "request_id": params.get("requestId", ""),
            "timestamp": datetime.now().isoformat(),
        })

    def handle_response(self, event: dict):
        """CDP Network.responseReceived callback."""
        params = event.get("params", {})
        resp = params.get("response", {})
        url = resp.get("url", "")
        mime = resp.get("mimeType", "")
        status = resp.get("status", 0)
        request_id = params.get("requestId", "")

        # We care about JSON/API responses
        if "json" not in mime and "/api/" not in url.lower():
            return

        entry = {
            "url": url,
            "mime": mime,
            "status": status,
            "request_id": request_id,
        }
        self.json_responses.append(entry)

        # Check if this looks like subscription data
        url_lower = url.lower()
        has_sub_data = any(kw in url_lower for kw in SUBSCRIPTION_KEYWORDS)

        endpoint = DiscoveredEndpoint(
            url=url,
            method="GET",
            content_type=mime,
            status_code=status,
            contains_subscription_data=has_sub_data,
        )
        self.discovered_apis.append(endpoint)

        if has_sub_data:
            log.info(f"💰 SUBSCRIPTION DATA endpoint: {url[:100]}")
        else:
            log.info(f"🔗 API endpoint: {url[:100]}")


async def run_recon(target_name: str, target_url: str) -> ReconResult:
    """
    Run reconnaissance on a single page.
    Opens with Pydoll, intercepts network, captures rendered HTML.
    """
    # Pydoll v2 API: Chrome class, ChromiumOptions, enable_network_events(), NetworkEvent enum
    from pydoll.browser.chromium import Chrome
    from pydoll.browser.options import ChromiumOptions
    from pydoll.protocol.network.events import NetworkEvent

    result = ReconResult(target_name=target_name, target_url=target_url)
    capture = NetworkCapture()
    start_time = time.time()

    # Configure stealth browser
    options = ChromiumOptions()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=ro-MD,ro,ru")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    from config import IN_DOCKER
    if IN_DOCKER:
        options.add_argument("--disable-gpu")

    log.info(f"🌐 RECON: {target_name} → {target_url}")

    try:
        async with Chrome(options=options) as browser:
            tab = await browser.start()

            # Enable network monitoring via CDP
            await tab.enable_network_events()

            # Attach event listeners for network capture (sync callbacks are fine)
            await tab.on(NetworkEvent.REQUEST_WILL_BE_SENT, capture.handle_request)
            await tab.on(NetworkEvent.RESPONSE_RECEIVED, capture.handle_response)

            # Navigate to target and wait for page load
            log.info("  ⏳ Navigating...")
            await tab.go_to(target_url)

            # Extra wait for SPA dynamic content
            await asyncio.sleep(PAGE_LOAD_WAIT)

            # Scroll through entire page to trigger lazy loading
            log.info("  📜 Scrolling to trigger lazy content...")
            for i in range(SCROLL_STEPS):
                scroll_pct = (i + 1) / SCROLL_STEPS
                await tab.execute_script(
                    f"window.scrollTo(0, document.body.scrollHeight * {scroll_pct})"
                )
                await asyncio.sleep(SCROLL_DELAY)

            # Scroll back to top
            await tab.execute_script("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

            # Capture fully rendered HTML and page title via built-in async properties
            rendered_html = await tab.page_source
            page_title = await tab.title

            result.rendered_html = rendered_html or ""
            result.page_title = page_title or ""

            # Try to fetch response bodies from discovered API endpoints using browser context
            for endpoint in capture.discovered_apis:
                try:
                    raw = await tab.execute_script(
                        f"""
                        (async () => {{
                            try {{
                                const r = await fetch("{endpoint.url}");
                                const t = await r.text();
                                return t.substring(0, 2000);
                            }} catch(e) {{
                                return "FETCH_ERROR: " + e.message;
                            }}
                        }})()
                        """,
                        await_promise=True,
                    )
                    body = _js_value(raw)
                    endpoint.sample_response_preview = str(body) if body else ""
                    endpoint.response_size_bytes = len(str(body)) if body else 0
                except Exception as e:
                    log.warning(f"  ⚠️ Could not fetch body for {endpoint.url[:60]}: {e}")

            result.discovered_endpoints = [ep.to_dict() for ep in capture.discovered_apis]
            result.all_network_requests = capture.requests
            result.success = True

            # Detect anti-scraping signals
            signals = await _detect_anti_scraping(tab)
            result.anti_scraping_signals = signals

    except ImportError:
        result.error = (
            "pydoll-python not installed. Run: pip install pydoll-python"
        )
        log.error(f"  ❌ {result.error}")
    except Exception as e:
        result.error = str(e)
        log.error(f"  ❌ Recon failed: {e}")

    result.duration_seconds = time.time() - start_time

    # Save rendered HTML to file
    if result.rendered_html:
        html_path = OUTPUT_DIR / f"recon_{target_name}.html"
        html_path.write_text(result.rendered_html, encoding="utf-8")
        log.info(f"  💾 HTML saved: {html_path} ({len(result.rendered_html):,} chars)")

    log.info(
        f"  📊 Requests: {len(capture.requests)} | "
        f"APIs: {len(capture.discovered_apis)} | "
        f"Duration: {result.duration_seconds:.1f}s"
    )

    return result


def _js_value(response) -> object:
    """Extract primitive value from execute_script EvaluateResponse dict."""
    try:
        return response["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def _detect_anti_scraping(tab) -> list[str]:
    """Detect anti-scraping measures on the current page."""
    signals = []

    checks = {
        "cloudflare": (
            "return document.querySelector('#cf-wrapper') !== null || "
            "document.querySelector('.cf-browser-verification') !== null"
        ),
        "recaptcha": (
            "return document.querySelector('.g-recaptcha') !== null || "
            "typeof grecaptcha !== 'undefined'"
        ),
        "webdriver_check": "return navigator.webdriver === true",
        "bot_detection_script": (
            "return document.querySelector('script[src*=\"bot\"]') !== null || "
            "document.querySelector('script[src*=\"fingerprint\"]') !== null"
        ),
        "devtools_detection": "return window.__devtools_was_detected === true",
    }

    for name, js_check in checks.items():
        try:
            raw = await tab.execute_script(js_check)
            detected = _js_value(raw)
            if detected:
                signals.append(name)
                log.warning(f"  🛡️ Anti-scraping detected: {name}")
        except Exception:
            pass

    if not signals:
        log.info("  ✅ No anti-scraping measures detected")

    return signals


async def run_full_recon() -> dict[str, ReconResult]:
    """Run recon on all target pages."""
    results: dict[str, ReconResult] = {}

    for name, url in TARGETS.items():
        log.info(f"\n{'='*60}")
        result = await run_recon(name, url)
        results[name] = result

        # Polite delay between pages
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        log.info(f"  ⏱️ Waiting {delay:.1f}s before next page...")
        await asyncio.sleep(delay)

    # Save consolidated recon report
    report: dict = {
        "recon_date": datetime.now().isoformat(),
        "targets_scanned": len(results),
        "results": {},
    }
    for name, res in results.items():
        report["results"][name] = {
            "url": res.target_url,
            "success": res.success,
            "page_title": res.page_title,
            "html_size": len(res.rendered_html),
            "api_endpoints_found": len(res.discovered_endpoints),
            "total_requests": len(res.all_network_requests),
            "anti_scraping": res.anti_scraping_signals,
            "error": res.error,
            "duration_s": res.duration_seconds,
            "endpoints": res.discovered_endpoints,
        }

    report_path = OUTPUT_DIR / "recon_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"\n📊 Recon report saved: {report_path}")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    asyncio.run(run_full_recon())
