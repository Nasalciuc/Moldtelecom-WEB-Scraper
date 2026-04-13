"""
Validator — merge and validate data from ALL cascade levels.

Reads: level3_api_replay.json, level4_ai_extraction.json
Writes: output/subscriptions_final.json
"""
import asyncio
import json
import logging
from datetime import datetime

from config import OUTPUT_DIR

log = logging.getLogger(__name__)

# Sanity bounds for Moldtelecom plan prices (MDL)
PRICE_MIN = 0.01
PRICE_MAX = 1000.0


def _sane(sub: dict) -> bool:
    """Sanity check: valid name AND price in range."""
    name = sub.get("name", "")
    price = sub.get("price_mdl", 0)
    if not name:
        return False
    if not (PRICE_MIN <= float(price or 0) <= PRICE_MAX):
        return False
    return True


async def validate() -> dict:
    """
    Merge and validate data from ALL cascade levels.
    Reads: level3_api_replay.json, level4_ai_extraction.json
    """
    from stealth import merge_subscriptions, quality_gate

    all_subs = []

    # Source 1: API replay data (Level 3)
    api_path = OUTPUT_DIR / "level3_api_replay.json"
    if api_path.exists():
        api_data = json.loads(api_path.read_text())
        api_subs = api_data.get("subscriptions", [])
        log.info(f"  API replay: {len(api_subs)} subscriptions")
        all_subs = merge_subscriptions(all_subs, api_subs)

    # Source 2: AI extraction (Level 4)
    ai_path = OUTPUT_DIR / "level4_ai_extraction.json"
    if ai_path.exists():
        ai_data = json.loads(ai_path.read_text())
        ai_subs = ai_data.get("subscriptions", [])
        log.info(f"  AI extraction: {len(ai_subs)} subscriptions")
        all_subs = merge_subscriptions(all_subs, ai_subs)

    # Sanity checks
    validated = [s for s in all_subs if _sane(s)]
    passed = quality_gate(validated)

    result = {
        "validation_date": datetime.now().isoformat(),
        "quality_gate_passed": passed,
        "total_merged": len(all_subs),
        "total_validated": len(validated),
        "subscriptions": validated,
    }

    path = OUTPUT_DIR / "subscriptions_final.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    log.info(f"  Final: {len(validated)} subscriptions -> {path}")
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    asyncio.run(validate())
