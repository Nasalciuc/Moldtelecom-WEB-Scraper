"""
API Replay — direct calls to discovered API endpoints.

Reads output/level3_api_endpoints.json (from Pydoll level 3),
filters endpoints that likely carry subscription data,
fetches them with browser-like headers via aiohttp,
and saves structured results to output/level3_api_replay.json.
"""
import asyncio
import json
import logging
import time
from datetime import datetime

import aiohttp

from config import OUTPUT_DIR, get_browser_headers
from stealth import human_delay, page_delay

log = logging.getLogger(__name__)

ENDPOINTS_FILE = OUTPUT_DIR / "level3_api_endpoints.json"
API_OUTPUT = OUTPUT_DIR / "level3_api_replay.json"

# aiohttp timeouts (seconds)
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 20


def _load_endpoints() -> list[dict]:
    """Load endpoints from level3_api_endpoints.json."""
    if not ENDPOINTS_FILE.exists():
        log.warning("level3_api_endpoints.json not found — Pydoll didn't run or found no endpoints.")
        return []

    try:
        data = json.loads(ENDPOINTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse level3_api_endpoints.json: {e}")
        return []

    if isinstance(data, list):
        return data
    return []


def _contains_subscription_data(payload: str) -> bool:
    """Heuristic check: does this JSON payload look like subscription data?"""
    keywords = [
        "abonament", "tarif", "pret", "price", "liberty", "star",
        "minute", "sms", "data_gb", "MDL", "lei", "subscription",
    ]
    lower = payload.lower()
    return any(kw in lower for kw in keywords)


async def _fetch_endpoint(
    session: aiohttp.ClientSession, endpoint: dict
) -> dict:
    """Fetch a single endpoint and return structured result."""
    url = endpoint.get("url", "")
    result = {
        "url": url,
        "status_code": 0,
        "content_type": "",
        "response_size_bytes": 0,
        "contains_subscription_data": False,
        "parsed_json": None,
        "raw_preview": "",
        "error": "",
        "fetched_at": datetime.now().isoformat(),
    }

    try:
        timeout = aiohttp.ClientTimeout(
            connect=CONNECT_TIMEOUT, sock_read=READ_TIMEOUT
        )
        async with session.get(url, timeout=timeout) as resp:
            result["status_code"] = resp.status
            result["content_type"] = resp.content_type or ""

            raw = await resp.text(encoding="utf-8", errors="replace")
            result["response_size_bytes"] = len(raw.encode("utf-8"))
            result["raw_preview"] = raw[:2000]

            if resp.status == 200 and "json" in (resp.content_type or ""):
                try:
                    parsed = json.loads(raw)
                    result["parsed_json"] = parsed
                    result["contains_subscription_data"] = _contains_subscription_data(
                        json.dumps(parsed, ensure_ascii=False)
                    )
                except json.JSONDecodeError:
                    result["error"] = "Invalid JSON in response"
            elif resp.status == 403:
                result["error"] = "HTTP 403 Forbidden — endpoint requires auth or blocks scrapers"
            elif resp.status == 404:
                result["error"] = "HTTP 404 Not Found"
            else:
                result["contains_subscription_data"] = _contains_subscription_data(raw)

    except asyncio.TimeoutError:
        result["error"] = f"Timeout after {READ_TIMEOUT}s"
    except aiohttp.ClientError as e:
        result["error"] = f"aiohttp error: {e}"
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"

    return result


async def run_api_replay() -> dict:
    """
    Main entry point: load endpoints, filter, fetch with stealth delays, save.
    Returns dict with list of subscriptions found.
    """
    log.info("  API Replay: fetching discovered endpoints...")

    all_endpoints = _load_endpoints()
    if not all_endpoints:
        log.info("  No endpoints to replay.")
        result = {"subscriptions": [], "raw_responses": [], "error": "No endpoints found"}
        API_OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    # Prioritise endpoints tagged as containing subscription data
    priority = [ep for ep in all_endpoints if ep.get("contains_subscription_data")]
    rest = [ep for ep in all_endpoints if not ep.get("contains_subscription_data")]
    ordered = priority + rest

    log.info(
        f"  Endpoints: {len(all_endpoints)} total, "
        f"{len(priority)} tagged as subscription-data"
    )

    raw_results: list[dict] = []
    all_subscriptions: list[dict] = []

    headers = get_browser_headers()
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(
        headers=headers, connector=connector
    ) as session:
        for ep in ordered:
            url = ep.get("url", "")
            log.info(f"  GET {url[:100]}")

            fetch_result = await _fetch_endpoint(session, ep)
            raw_results.append(fetch_result)

            if fetch_result["contains_subscription_data"] and fetch_result["parsed_json"]:
                subs = _extract_subscriptions_from_json(
                    fetch_result["parsed_json"], url
                )
                if subs:
                    log.info(f"  Found {len(subs)} subscription(s)")
                    all_subscriptions.extend(subs)

            if fetch_result["error"]:
                log.warning(f"  {fetch_result['error']}")

            # Stealth delay between requests
            await human_delay("api replay")

    output = {
        "extraction_date": datetime.now().isoformat(),
        "endpoints_fetched": len(raw_results),
        "subscriptions": all_subscriptions,
        "raw_responses": raw_results,
    }

    API_OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"  Saved {len(all_subscriptions)} subscriptions -> {API_OUTPUT}")

    return output


def _extract_subscriptions_from_json(data: object, source_url: str) -> list[dict]:
    """
    Best-effort extraction of subscription records from an arbitrary JSON payload.
    Handles both lists and nested dict structures.
    """
    subscriptions: list[dict] = []

    def _process_item(item: dict) -> dict | None:
        """Try to map a dict to a Subscription-like structure."""
        name = (
            item.get("name") or item.get("title") or
            item.get("denumire") or item.get("tariff_name") or ""
        )
        price = (
            item.get("price") or item.get("pret") or
            item.get("price_mdl") or item.get("cost") or 0
        )
        if not name and not price:
            return None

        return {
            "name": str(name),
            "price_mdl": float(price) if price else 0.0,
            "price_promo_mdl": item.get("price_promo") or item.get("pret_promo"),
            "minutes_in_network": str(item.get("minutes_in_network", "")),
            "minutes_national": str(item.get("minutes_national", "")),
            "minutes_international": str(item.get("minutes_international", "")),
            "sms_in_network": str(item.get("sms_in_network", "")),
            "data_gb": str(item.get("data_gb", "") or item.get("internet", "")),
            "extra_features": item.get("extra_features", []),
            "contract_months": int(item.get("contract_months", 0)),
            "promo_conditions": str(item.get("promo_conditions", "")),
            "source_url": source_url,
            "source_method": "api_direct",
            "extracted_at": datetime.now().isoformat(),
        }

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rec = _process_item(item)
                if rec:
                    subscriptions.append(rec)
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("subscriptions", "plans", "tariffs", "abonamente", "items", "data"):
            if isinstance(data.get(key), list):
                for item in data[key]:
                    if isinstance(item, dict):
                        rec = _process_item(item)
                        if rec:
                            subscriptions.append(rec)
                break

    return subscriptions


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    asyncio.run(run_api_replay())
