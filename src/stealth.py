"""
Shared stealth utilities used by all cascade levels.
Handles human-like delays, quality gates, and data merging.
"""
import asyncio
import random
import logging
from config import (
    DELAY_BETWEEN_PAGES_MIN, DELAY_BETWEEN_PAGES_MAX,
    DELAY_BETWEEN_ACTIONS_MIN, DELAY_BETWEEN_ACTIONS_MAX,
    SUBSCRIPTION_KEYWORDS, MIN_SUBSCRIPTIONS, MIN_PRICE_MDL,
)

log = logging.getLogger(__name__)


async def human_delay(context: str = ""):
    """Random delay between small actions (scroll, click). Always call between actions."""
    delay = random.uniform(DELAY_BETWEEN_ACTIONS_MIN, DELAY_BETWEEN_ACTIONS_MAX)
    if context:
        log.debug(f"  waiting {delay:.1f}s ({context})")
    await asyncio.sleep(delay)


async def page_delay(context: str = ""):
    """Longer delay between page loads. Mimics human reading time."""
    delay = random.uniform(DELAY_BETWEEN_PAGES_MIN, DELAY_BETWEEN_PAGES_MAX)
    log.info(f"  Waiting {delay:.1f}s before next page ({context})")
    await asyncio.sleep(delay)


def quality_gate(subscriptions: list) -> bool:
    """
    Check if extracted data is sufficient to stop the cascade.
    Returns True if we have enough quality data.
    """
    if not subscriptions:
        return False

    valid = [
        s for s in subscriptions
        if s.get("name", "").strip()
        and isinstance(s.get("price_mdl", 0), (int, float))
        and s.get("price_mdl", 0) >= MIN_PRICE_MDL
    ]

    if len(valid) < MIN_SUBSCRIPTIONS:
        log.info(f"  Quality gate: {len(valid)}/{MIN_SUBSCRIPTIONS} valid plans -> FAIL")
        return False

    log.info(f"  Quality gate: {len(valid)} valid plans -> PASS")
    return True


def html_has_content(html: str) -> bool:
    """Check if HTML has actual rendered content (not an empty SPA shell)."""
    if not html or len(html) < 3000:
        return False
    html_lower = html.lower()
    keyword_hits = sum(1 for kw in SUBSCRIPTION_KEYWORDS if kw in html_lower)
    return keyword_hits >= 3


def merge_subscriptions(existing: list, new_data: list) -> list:
    """
    Merge new subscriptions into existing list with fuzzy deduplication.
    Keeps the version with more fields filled in.
    """
    seen = {}
    for s in existing:
        key = _normalize_name(s.get("name", ""))
        if key:
            seen[key] = s

    added = 0
    for s in new_data:
        key = _normalize_name(s.get("name", ""))
        if not key:
            continue
        if key in seen:
            if _completeness(s) > _completeness(seen[key]):
                seen[key] = s
        else:
            seen[key] = s
            added += 1

    if added:
        log.info(f"  Merge: +{added} new, {len(seen)} total")
    return list(seen.values())


def _normalize_name(name: str) -> str:
    """Normalize plan name for dedup: 'Liberty 190' == 'liberty190'."""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "").strip()


def _completeness(sub: dict) -> int:
    """Score how many fields are filled in a subscription record."""
    score = 0
    for field in ["name", "price_mdl", "minutes_in_network", "minutes_national",
                   "sms_in_network", "data_gb", "contract_months"]:
        if sub.get(field):
            score += 1
    return score
