"""
AI Extraction via Claude Code CLI.
Uses `claude -p` (Pro/Max plan) instead of Anthropic API SDK.
No API key needed — authenticated via `claude login` OAuth.
"""
import asyncio
import json
import re
import time
import logging
from datetime import datetime
from pathlib import Path

from config import CLAUDE_CLI, CLAUDE_MODEL, CLAUDE_TIMEOUT, OUTPUT_DIR

log = logging.getLogger(__name__)

SUBSCRIPTION_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "subscriptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price_mdl": {"type": "number"},
                    "price_promo_mdl": {"type": ["number", "null"]},
                    "minutes_in_network": {"type": "string"},
                    "minutes_national": {"type": "string"},
                    "minutes_international": {"type": "string"},
                    "sms_in_network": {"type": "string"},
                    "data_gb": {"type": "string"},
                    "extra_features": {"type": "array", "items": {"type": "string"}},
                    "contract_months": {"type": "integer"},
                    "promo_conditions": {"type": "string"}
                },
                "required": ["name", "price_mdl"]
            }
        }
    },
    "required": ["subscriptions"]
})

SYSTEM_PROMPT = """You are a data extraction specialist for Moldtelecom, Moldova's telecom operator.
From the provided HTML, extract ALL mobile subscription plans.
Prices are in MDL (Moldovan Lei).
"Nelimitat min. și SMS în rețea" means minutes_in_network: "Nelimitat" AND sms_in_network: "Nelimitat".
"min naționale" = minutes_national. "min internaționale" = minutes_international.
Put promo details in promo_conditions. Extract EVERY plan. Do not skip any."""


def _clean_html(html: str) -> str:
    """Strip scripts, styles, SVGs, comments, data-attrs, compress whitespace."""
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.I)
    html = re.sub(r'<svg[^>]*>[\s\S]*?</svg>', '', html, flags=re.I)
    html = re.sub(r'<noscript[^>]*>[\s\S]*?</noscript>', '', html, flags=re.I)
    html = re.sub(r'<!--[\s\S]*?-->', '', html)
    html = re.sub(r'\s+data-[\w-]+="[^"]*"', '', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()


async def extract_with_claude_cli(html_content: str, page_name: str = "") -> dict:
    """
    Send HTML to Claude Code CLI for structured extraction.
    Prompt piped via stdin. --json-schema guarantees valid JSON output.
    """
    cleaned = _clean_html(html_content)
    if len(cleaned) > 80000:
        cleaned = cleaned[:80000] + "\n[TRUNCATED]"

    prompt = f"""{SYSTEM_PROMPT}

Page: {page_name}

HTML content:
{cleaned}"""

    log.info(f"🤖 Sending {len(cleaned):,} chars to Claude CLI ({page_name})...")
    start = time.time()

    try:
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI,
            "-p", "-",
            "--output-format", "json",
            "--json-schema", SUBSCRIPTION_SCHEMA,
            "--model", CLAUDE_MODEL,
            "--bare",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode("utf-8")),
            timeout=CLAUDE_TIMEOUT,
        )

        duration = time.time() - start

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            log.error(f"  ❌ Claude CLI error (code {process.returncode}): {error_msg}")
            return _fallback_regex(html_content)

        output = stdout.decode("utf-8", errors="replace").strip()

        try:
            response_data = json.loads(output)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                response_data = json.loads(json_match.group())
            else:
                log.error("  ❌ Could not parse Claude CLI output")
                return _fallback_regex(html_content)

        # Claude CLI --output-format json wraps in {result, session_id, ...}
        if "structured_output" in response_data:
            result = response_data["structured_output"]
        elif "result" in response_data:
            result_field = response_data["result"]
            if isinstance(result_field, str):
                try:
                    result = json.loads(result_field)
                except json.JSONDecodeError:
                    result = {"subscriptions": [], "note": result_field[:500]}
            elif isinstance(result_field, dict):
                result = result_field
            else:
                result = {"subscriptions": []}
        else:
            result = response_data

        n = len(result.get("subscriptions", []))
        log.info(f"  ✅ Claude CLI: {n} subscriptions in {duration:.1f}s")
        return result

    except asyncio.TimeoutError:
        log.error(f"  ⏰ Claude CLI timeout ({CLAUDE_TIMEOUT}s)")
        return _fallback_regex(html_content)
    except FileNotFoundError:
        log.error("  ❌ Claude Code CLI not found!")
        log.error("     Install: npm install -g @anthropic-ai/claude-code")
        log.error("     Login:   claude login")
        return _fallback_regex(html_content)
    except Exception as e:
        log.error(f"  ❌ Claude CLI error: {e}")
        return _fallback_regex(html_content)


def _fallback_regex(html: str) -> dict:
    """Regex fallback when Claude CLI unavailable."""
    log.info("  🔧 Using regex fallback...")
    subscriptions = []
    patterns = [
        r'(Liberty\s*Plus?\s*\d+)',
        r'(Star\s*\d+)',
        r'(Smart\s*Connect\s*\d+)',
        r'(MConnect\s*\d+)',
    ]
    for pattern in patterns:
        for name in set(re.findall(pattern, html, re.I)):
            price_match = re.search(
                rf'{re.escape(name)}[\s\S]{{0,500}}?(\d+)\s*(?:MDL|lei)', html, re.I
            )
            subscriptions.append({
                "name": name.strip(),
                "price_mdl": float(price_match.group(1)) if price_match else 0.0,
                "source_method": "regex_fallback",
            })
    log.info(f"  🔧 Regex found {len(subscriptions)} plans")
    return {"subscriptions": subscriptions, "method": "regex_fallback"}


async def extract_all_pages() -> dict:
    """Process all rendered HTML files from recon phase."""
    all_subs = []
    for html_file in sorted(OUTPUT_DIR.glob("recon_*.html")):
        page_name = html_file.stem.replace("recon_", "")
        log.info(f"\n📄 Processing: {page_name}")
        html = html_file.read_text(encoding="utf-8")
        result = await extract_with_claude_cli(html, page_name)
        for sub in result.get("subscriptions", []):
            sub["source_page"] = page_name
            sub["source_method"] = sub.get("source_method", "claude_cli")
            sub["extracted_at"] = datetime.now().isoformat()
            all_subs.append(sub)

    output = {
        "extraction_date": datetime.now().isoformat(),
        "method": "claude_cli",
        "total": len(all_subs),
        "subscriptions": all_subs,
    }
    output_path = OUTPUT_DIR / "ai_extraction.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"\n✅ AI extraction: {len(all_subs)} subscriptions → {output_path}")
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(extract_all_pages())
