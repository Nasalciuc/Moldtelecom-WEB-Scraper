"""
Moldtelecom AI Scraping Agent — 4-Level Cascade Orchestrator

Levels:
  1. HTTP Probe — baseline, shows SPA protection
  2. Scrapling StealthyFetcher — PRIMARY, anti-bot bypass
  3. Pydoll CDP — OPTIONAL, network interception & API discovery
  4. Claude CLI AI — extraction from best available HTML

Each level adds data. Tools are optional — cascade degrades gracefully.

Usage:
    python src/agent.py                # Full cascade
    python src/agent.py --level 2      # Run specific level only
    python src/agent.py --report       # Only regenerate report
    python src/agent.py --validate     # Only merge and validate
"""
import asyncio
import sys
import time
import logging
import random
from datetime import datetime
from config import OUTPUT_DIR, DELAY_BETWEEN_LEVELS, check_claude_cli

log = logging.getLogger(__name__)


async def run_cascade():
    start = time.time()
    log.info("Moldtelecom AI Scraping Agent — 4-Level Cascade")
    log.info("=" * 60)

    # Pre-flight tool checks
    scrapling_ok, pydoll_ok, claude_ok = _check_tools()

    if not scrapling_ok and not pydoll_ok:
        log.error("Need at least Scrapling OR Pydoll installed!")
        log.error("   pip install scrapling       (recommended)")
        log.error("   pip install pydoll-python    (alternative)")
        return

    # ═══ LEVEL 1: HTTP Probe (always runs) ═══
    log.info(f"\n{'='*60}")
    log.info("LEVEL 1: Direct HTTP Probe")
    log.info("-" * 40)
    from level1_http import run_level1
    try:
        l1 = await run_level1()
    except Exception as e:
        log.error(f"Level 1 failed: {e}")
        l1 = {}
    await _level_pause()

    # ═══ LEVEL 2: Scrapling (PRIMARY) ═══
    log.info(f"\n{'='*60}")
    log.info("LEVEL 2: Scrapling Stealth Fetch")
    log.info("-" * 40)
    if scrapling_ok:
        from level2_scrapling import run_level2
        try:
            l2 = await run_level2()
        except Exception as e:
            log.error(f"Level 2 failed: {e}")
            l2 = {"available": False, "error": str(e)}
    else:
        log.info("  Scrapling not installed — skipping")
        l2 = {"available": False}
    await _level_pause()

    # ═══ LEVEL 3: Pydoll CDP (OPTIONAL) ═══
    log.info(f"\n{'='*60}")
    log.info("LEVEL 3: Pydoll Network Interception")
    log.info("-" * 40)
    if pydoll_ok:
        from level3_pydoll import run_level3
        try:
            l3 = await run_level3()
        except Exception as e:
            log.error(f"Level 3 failed: {e}")
            l3 = {"available": False, "error": str(e)}

        # API replay if endpoints were discovered
        try:
            from api_replay import run_api_replay
            await run_api_replay()
        except Exception as e:
            log.error(f"API replay failed: {e}")
    else:
        log.info("  Pydoll not installed — skipping (optional)")
        l3 = {"available": False}
    await _level_pause()

    # ═══ LEVEL 4: Claude CLI AI Extraction ═══
    log.info(f"\n{'='*60}")
    log.info("LEVEL 4: AI Extraction (Claude CLI)")
    log.info("-" * 40)
    from level4_ai import run_level4
    try:
        l4 = await run_level4()
    except Exception as e:
        log.error(f"Level 4 failed: {e}")
        l4 = {"subscriptions": []}

    # ═══ FINAL: Validate + Report ═══
    log.info(f"\n{'='*60}")
    log.info("FINAL: Validation + Report")
    log.info("-" * 40)

    from validator import validate
    try:
        final = await validate()
    except Exception as e:
        log.error(f"Validation failed: {e}")
        final = {}

    from report_generator import generate_report
    try:
        report_path = generate_report()
        log.info(f"Report: {report_path}")
    except Exception as e:
        log.error(f"Report generation failed: {e}")

    duration = time.time() - start
    subs = final.get("total_validated", 0)
    gate = "PASSED" if final.get("quality_gate_passed") else "FAILED"
    log.info(f"\n{'='*60}")
    log.info(f"CASCADE COMPLETE in {duration:.1f}s")
    log.info(f"Subscriptions: {subs} | Quality gate: {gate}")
    log.info(f"Output: {OUTPUT_DIR}/")
    log.info(f"{'='*60}")


def _check_tools() -> tuple[bool, bool, bool]:
    """Check which tools are available."""
    scrapling_ok = False
    try:
        from scrapling.fetchers import StealthyFetcher
        scrapling_ok = True
    except ImportError:
        pass

    pydoll_ok = False
    try:
        from pydoll.browser.chromium import Chrome
        pydoll_ok = True
    except ImportError:
        pass

    claude_ok = check_claude_cli()

    log.info("Tool check:")
    log.info(f"   Scrapling (Level 2):  {'ready' if scrapling_ok else 'not installed'}")
    log.info(f"   Pydoll (Level 3):     {'ready' if pydoll_ok else 'not installed (optional)'}")
    log.info(f"   Claude CLI (Level 4): {'ready' if claude_ok else 'not found (regex fallback)'}")

    return scrapling_ok, pydoll_ok, claude_ok


async def _level_pause():
    """Stealth pause between cascade levels."""
    delay = DELAY_BETWEEN_LEVELS + random.uniform(0, 5)
    log.info(f"\n  Pausing {delay:.0f}s between levels (stealth)...")
    await asyncio.sleep(delay)


async def main():
    args = sys.argv[1:]
    if "--level" in args:
        idx = args.index("--level")
        level = args[idx + 1] if idx + 1 < len(args) else "0"
        if level == "1":
            from level1_http import run_level1
            await run_level1()
        elif level == "2":
            from level2_scrapling import run_level2
            await run_level2()
        elif level == "3":
            from level3_pydoll import run_level3
            await run_level3()
        elif level == "4":
            from level4_ai import run_level4
            await run_level4()
    elif "--report" in args:
        from report_generator import generate_report
        generate_report()
    elif "--validate" in args:
        from validator import validate
        await validate()
    else:
        await run_cascade()


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(OUTPUT_DIR / f"agent_{datetime.now():%Y%m%d_%H%M%S}.log"),
        ],
    )
    asyncio.run(main())
