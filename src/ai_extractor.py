"""
AI Extractor — Claude-based semantic extraction from rendered HTML.

Fallback / complement to api_extractor. Reads rendered HTML files
saved by recon.py, cleans them, sends to Claude API, and parses the
structured JSON response.

If ANTHROPIC_API_KEY is not set, falls back to a simple regex extractor.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from config import ANTHROPIC_API_KEY, OUTPUT_DIR

log = logging.getLogger(__name__)

AI_OUTPUT = OUTPUT_DIR / "ai_extraction.json"

# Claude model to use
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096

# Maximum HTML chars sent to Claude (keeps within token limits)
HTML_CHAR_LIMIT = 80_000

SYSTEM_PROMPT = """You are a data extraction specialist for Moldtelecom, Moldova's telecom operator.

From the provided HTML content, extract ALL mobile subscription plans.

Return ONLY valid JSON, no markdown, no explanation. Format:
{
  "subscriptions": [
    {
      "name": "Plan name (e.g. Liberty 190, Star 150)",
      "price_mdl": 190.0,
      "price_promo_mdl": null,
      "minutes_in_network": "Nelimitat",
      "minutes_national": "30",
      "minutes_international": "50",
      "sms_in_network": "Nelimitat",
      "data_gb": "15 GB",
      "extra_features": ["CLIP", "Roaming EU"],
      "contract_months": 6,
      "promo_conditions": "50 lei reducere cu Internet Fix"
    }
  ]
}

RULES:
- Prices are in MDL (Moldovan Lei)
- "Nelimitat min. și SMS în rețea" = minutes_in_network: "Nelimitat", sms_in_network: "Nelimitat"
- "min naționale" = minutes to other national operators = minutes_national
- If no subscriptions found, return {"subscriptions": [], "note": "reason"}
- Return ONLY the JSON object, nothing else"""


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------

_RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.S | re.I)
_RE_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.S | re.I)
_RE_SVG = re.compile(r"<svg[^>]*>.*?</svg>", re.S | re.I)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RE_WHITESPACE = re.compile(r"\s{2,}")


def _clean_html(raw_html: str) -> str:
    """Strip non-content elements and compress whitespace."""
    html = _RE_SCRIPT.sub("", raw_html)
    html = _RE_STYLE.sub("", html)
    html = _RE_SVG.sub("", html)
    html = _RE_COMMENT.sub("", html)
    html = _RE_WHITESPACE.sub(" ", html)
    return html.strip()[:HTML_CHAR_LIMIT]


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_claude_json(text: str) -> dict:
    """
    Parse Claude's response which may be wrapped in ```json ... ``` fences.
    Returns parsed dict or raises ValueError.
    """
    # Try raw first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Last resort: find first { ... }
    brace_match = re.search(r"\{[\s\S]+\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from Claude response: {text[:200]}")


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def _call_claude(html_content: str) -> dict:
    """Synchronous Claude API call (wrapped in asyncio.to_thread below)."""
    import anthropic  # imported here so missing package gives a clear error

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": html_content}],
    )
    block = message.content[0]
    text: str = getattr(block, "text", "") or str(block)
    return _parse_claude_json(text)


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------

_RE_PLAN_NAME = re.compile(
    r"\b(Liberty\s*\d+|Star\s*\d+|Smart\s*Connect\s*\d*|Smart\s*\d+)\b", re.I
)
_RE_PRICE = re.compile(r"(\d{2,4})\s*(?:MDL|lei)", re.I)


def _regex_fallback(html: str, source_url: str) -> list[dict]:
    """Simple regex extraction when no API key is configured."""
    subscriptions: list[dict] = []
    names = _RE_PLAN_NAME.findall(html)
    prices = _RE_PRICE.findall(html)

    for i, name in enumerate(names):
        price = float(prices[i]) if i < len(prices) else 0.0
        subscriptions.append({
            "name": name.strip(),
            "price_mdl": price,
            "price_promo_mdl": None,
            "minutes_in_network": "",
            "minutes_national": "",
            "minutes_international": "",
            "sms_in_network": "",
            "data_gb": "",
            "extra_features": [],
            "contract_months": 0,
            "promo_conditions": "",
            "source_url": source_url,
            "source_method": "regex_fallback",
            "extracted_at": datetime.now().isoformat(),
        })
    return subscriptions


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

async def _extract_from_file(html_path: Path, use_claude: bool) -> dict:
    """Extract subscriptions from a single rendered HTML file."""
    target_name = html_path.stem.replace("recon_", "")
    source_url = html_path.as_uri()

    log.info(f"  📄 Processing {html_path.name} ({html_path.stat().st_size:,} bytes)")
    raw_html = html_path.read_text(encoding="utf-8", errors="replace")
    cleaned = _clean_html(raw_html)
    log.info(f"     Cleaned HTML: {len(cleaned):,} chars")

    start = time.time()

    if use_claude:
        try:
            parsed = await asyncio.to_thread(_call_claude, cleaned)
            subs = parsed.get("subscriptions", [])
            # Annotate with metadata
            now = datetime.now().isoformat()
            for sub in subs:
                sub.setdefault("source_url", source_url)
                sub.setdefault("source_method", "ai_claude")
                sub.setdefault("extracted_at", now)
            confidence = "high" if subs else "medium"
            error = parsed.get("note", "")
            log.info(f"     🤖 Claude found {len(subs)} subscription(s)")
        except Exception as e:
            log.error(f"     ❌ Claude API error: {e}")
            subs = []
            confidence = "low"
            error = str(e)
    else:
        log.warning("     ⚠️ No ANTHROPIC_API_KEY — using regex fallback")
        subs = _regex_fallback(cleaned, source_url)
        confidence = "low"
        error = "ANTHROPIC_API_KEY not set"
        log.info(f"     🔍 Regex found {len(subs)} subscription(s)")

    return {
        "target": target_name,
        "html_file": str(html_path),
        "subscriptions": subs,
        "confidence": confidence,
        "duration_seconds": round(time.time() - start, 2),
        "error": error,
    }


async def extract_all_pages() -> dict:
    """
    Extract subscription data from all rendered HTML files saved by recon.

    Returns merged dict with all subscriptions and per-page details.
    """
    log.info("🤖 Starting AI extraction phase...")

    html_files = list(OUTPUT_DIR.glob("recon_*.html"))
    if not html_files:
        log.warning("No recon_*.html files found — run recon first.")
        result = {
            "extraction_date": datetime.now().isoformat(),
            "pages_processed": 0,
            "subscriptions": [],
            "per_page": [],
            "error": "No HTML files found",
        }
        AI_OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    use_claude = bool(ANTHROPIC_API_KEY)
    if not use_claude:
        log.warning("ANTHROPIC_API_KEY not set — regex fallback will be used for all pages")

    per_page: list[dict] = []
    all_subscriptions: list[dict] = []

    for html_file in html_files:
        page_result = await _extract_from_file(html_file, use_claude)
        per_page.append(page_result)
        all_subscriptions.extend(page_result["subscriptions"])

    output = {
        "extraction_date": datetime.now().isoformat(),
        "pages_processed": len(html_files),
        "subscriptions": all_subscriptions,
        "per_page": per_page,
    }

    AI_OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(
        f"  💾 AI extraction complete: {len(all_subscriptions)} subscriptions "
        f"from {len(html_files)} pages → {AI_OUTPUT}"
    )

    return output


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    asyncio.run(extract_all_pages())
