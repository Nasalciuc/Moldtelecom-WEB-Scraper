"""
Validator — cross-validate subscriptions from API and AI extraction.

Rules:
- Same plan name in both sources → HIGH confidence, prefer API data (more precise)
- Plan found in only one source → MEDIUM confidence, flagged for review
- Sanity checks applied to all records:
    - price_mdl must be > 0 and < 1000
    - name must not be empty
    - must have at least minutes_in_network OR data_gb
- If api_data empty → use ai_data entirely
- If ai_data empty → use api_data entirely

Saves output/subscriptions_validated.json.
"""
import asyncio
import json
import logging
from datetime import datetime

from config import OUTPUT_DIR

log = logging.getLogger(__name__)

VALIDATED_OUTPUT = OUTPUT_DIR / "subscriptions_validated.json"

# Sanity bounds for Moldtelecom plan prices (MDL)
PRICE_MIN = 0.01
PRICE_MAX = 1000.0


def _normalise_name(name: str) -> str:
    """Lowercase + strip for fuzzy name matching."""
    return name.lower().strip()


def _sanity_check(sub: dict) -> tuple[bool, list[str]]:
    """
    Return (is_valid, list_of_issues).
    A record is considered valid only if no critical issue is found.
    """
    issues: list[str] = []

    name = sub.get("name", "")
    price = sub.get("price_mdl", 0)
    minutes = sub.get("minutes_in_network", "")
    data = sub.get("data_gb", "")

    if not name:
        issues.append("empty name")
    if not (PRICE_MIN <= float(price or 0) <= PRICE_MAX):
        issues.append(f"price out of range: {price}")
    if not minutes and not data:
        issues.append("no minutes_in_network or data_gb")

    return len(issues) == 0, issues


async def validate(api_data: dict, ai_data: dict) -> dict:
    """
    Cross-check subscriptions from two sources and return merged result.

    Parameters
    ----------
    api_data : dict
        Output of api_extractor.extract_from_apis()
    ai_data : dict
        Output of ai_extractor.extract_all_pages()

    Returns
    -------
    dict
        {"subscriptions": [...], "validation_stats": {...}}
    """
    api_subs: list[dict] = api_data.get("subscriptions", [])
    ai_subs: list[dict] = ai_data.get("subscriptions", [])

    log.info(
        f"✅ Validation: {len(api_subs)} API record(s) | {len(ai_subs)} AI record(s)"
    )

    # --- Fast-path: one source is empty ---
    if not api_subs and not ai_subs:
        log.warning("  Both sources empty — nothing to validate.")
        result = _build_output([], api_subs, ai_subs, {})
        _save(result)
        return result

    if not api_subs:
        log.info("  API extraction empty — using AI data only.")
        validated = _apply_sanity(ai_subs, "ai_only")
        result = _build_output(validated, api_subs, ai_subs, {})
        _save(result)
        return result

    if not ai_subs:
        log.info("  AI extraction empty — using API data only.")
        validated = _apply_sanity(api_subs, "api_only")
        result = _build_output(validated, api_subs, ai_subs, {})
        _save(result)
        return result

    # --- Cross-validation ---
    # Index AI subs by normalised name
    ai_by_name: dict[str, dict] = {
        _normalise_name(s.get("name", "")): s for s in ai_subs
    }

    merged: list[dict] = []
    matched_ai_names: set[str] = set()
    stats: dict[str, int] = {"high": 0, "medium_api_only": 0, "medium_ai_only": 0, "failed_sanity": 0}

    for api_sub in api_subs:
        name_key = _normalise_name(api_sub.get("name", ""))
        ai_match = ai_by_name.get(name_key)

        if ai_match:
            # Both sources agree on this plan — HIGH confidence
            record = dict(api_sub)
            record["confidence"] = "high"
            record["cross_validated"] = True
            matched_ai_names.add(name_key)
            stats["high"] += 1
        else:
            # Only in API source
            record = dict(api_sub)
            record["confidence"] = "medium"
            record["cross_validated"] = False
            record["review_note"] = "only in api_direct extraction"
            stats["medium_api_only"] += 1

        valid, issues = _sanity_check(record)
        if valid:
            merged.append(record)
        else:
            log.warning(f"  ⚠️ Sanity fail [{record.get('name')}]: {issues}")
            record["sanity_issues"] = issues
            record["confidence"] = "low"
            merged.append(record)  # keep but flag
            stats["failed_sanity"] += 1

    # Add AI-only plans not matched by API
    for ai_sub in ai_subs:
        name_key = _normalise_name(ai_sub.get("name", ""))
        if name_key not in matched_ai_names:
            record = dict(ai_sub)
            record["confidence"] = "medium"
            record["cross_validated"] = False
            record["review_note"] = "only in ai_claude extraction"
            stats["medium_ai_only"] += 1

            valid, issues = _sanity_check(record)
            if not valid:
                record["sanity_issues"] = issues
                record["confidence"] = "low"
                stats["failed_sanity"] += 1

            merged.append(record)

    log.info(
        f"  📊 Stats — high: {stats['high']} | "
        f"api-only: {stats['medium_api_only']} | "
        f"ai-only: {stats['medium_ai_only']} | "
        f"failed sanity: {stats['failed_sanity']}"
    )

    result = _build_output(merged, api_subs, ai_subs, stats)
    _save(result)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_sanity(subs: list[dict], source_label: str) -> list[dict]:
    """Run sanity checks on a list without cross-validation."""
    out: list[dict] = []
    for sub in subs:
        record = dict(sub)
        record["cross_validated"] = False
        valid, issues = _sanity_check(record)
        if valid:
            record["confidence"] = "medium"
        else:
            record["confidence"] = "low"
            record["sanity_issues"] = issues
        record["review_note"] = f"single-source: {source_label}"
        out.append(record)
    return out


def _build_output(
    validated: list[dict],
    api_subs: list[dict],
    ai_subs: list[dict],
    stats: dict,
) -> dict:
    return {
        "validation_date": datetime.now().isoformat(),
        "api_input_count": len(api_subs),
        "ai_input_count": len(ai_subs),
        "validated_count": len(validated),
        "validation_stats": stats,
        "subscriptions": validated,
    }


def _save(data: dict) -> None:
    VALIDATED_OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(
        f"  💾 Validated data saved: {VALIDATED_OUTPUT} "
        f"({data['validated_count']} records)"
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # Allow standalone test: python validator.py (reads existing output files)
    api_path = OUTPUT_DIR / "api_extraction.json"
    ai_path = OUTPUT_DIR / "ai_extraction.json"

    api_data = json.loads(api_path.read_text()) if api_path.exists() else {}
    ai_data = json.loads(ai_path.read_text()) if ai_path.exists() else {}

    asyncio.run(validate(api_data, ai_data))
