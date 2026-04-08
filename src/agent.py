"""
Moldtelecom AI Scraping Agent — Main Orchestrator

Usage:
    python src/agent.py                 # Full pipeline
    python src/agent.py --recon         # Only recon phase
    python src/agent.py --extract       # Only extraction (needs recon data)
    python src/agent.py --report        # Only report (needs extraction data)
"""
import asyncio
import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

log = logging.getLogger(__name__)


async def run_full_pipeline():
    """Execute all phases sequentially."""
    start = time.time()
    log.info("🚀 Moldtelecom AI Scraping Agent — START")
    log.info("=" * 60)

    from config import check_claude_cli
    if check_claude_cli():
        log.info("✅ Claude Code CLI ready")
    else:
        log.warning("⚠️  Claude CLI not found — AI extraction will use regex fallback")
        log.warning("   Install: npm install -g @anthropic-ai/claude-code")
        log.warning("   Login:   claude login")

    # Phase 1: Sitemap Analysis
    log.info("\n📡 PHASE 1: Sitemap Analysis")
    log.info("-" * 40)
    from sitemap_analyzer import analyze_sitemap
    try:
        sitemap_data = await analyze_sitemap()
        log.info(
            f"   ✅ {sitemap_data.get('total_urls_discovered', 0)} URLs discovered"
        )
    except Exception as e:
        log.error(f"Sitemap failed: {e}")
        sitemap_data = {}

    # Phase 2: Stealth Recon + Network Interception
    log.info("\n🌐 PHASE 2: Stealth Recon + Network Interception")
    log.info("-" * 40)
    from recon import run_full_recon
    try:
        recon_results = await run_full_recon()
        total_endpoints = sum(
            len(r.discovered_endpoints) for r in recon_results.values()
        )
        log.info(f"   ✅ {len(recon_results)} pages scanned, {total_endpoints} endpoints found")
    except Exception as e:
        log.error(f"Recon failed: {e}")
        recon_results = {}

    # Phase 3a: Direct API Extraction
    log.info("\n⚡ PHASE 3a: Direct API Extraction")
    log.info("-" * 40)
    from api_extractor import extract_from_apis
    try:
        api_data = await extract_from_apis()
        log.info(f"   ✅ {len(api_data.get('subscriptions', []))} subscriptions via API")
    except Exception as e:
        log.error(f"API extraction failed: {e}")
        api_data = {"subscriptions": []}

    # Phase 3b: AI Extraction (fallback/complement)
    log.info("\n🤖 PHASE 3b: AI Extraction (Claude)")
    log.info("-" * 40)
    from ai_extractor import extract_all_pages
    try:
        ai_data = await extract_all_pages()
        log.info(f"   ✅ {len(ai_data.get('subscriptions', []))} subscriptions via AI")
    except Exception as e:
        log.error(f"AI extraction failed: {e}")
        ai_data = {"subscriptions": []}

    # Phase 4: Cross-Validation
    log.info("\n✅ PHASE 4: Cross-Validation")
    log.info("-" * 40)
    from validator import validate
    try:
        validated = await validate(api_data, ai_data)
        log.info(f"   ✅ {validated.get('validated_count', 0)} records validated")
    except Exception as e:
        log.error(f"Validation failed: {e}")
        # Fall back to whichever source has data
        validated = api_data if api_data.get("subscriptions") else ai_data

    # Phase 5: Report Generation
    log.info("\n📊 PHASE 5: Report Generation")
    log.info("-" * 40)
    from report_generator import generate_report
    try:
        report_path = generate_report()
        log.info(f"   📄 Report: {report_path}")
    except Exception as e:
        log.error(f"Report generation failed: {e}")

    duration = time.time() - start
    log.info(f"\n{'=' * 60}")
    log.info(f"✅ PIPELINE COMPLETE in {duration:.1f}s")
    log.info(f"📂 All output in: {OUTPUT_DIR}/")
    log.info(f"{'=' * 60}")

    _print_summary()


def _print_summary():
    """Print a brief summary of output files."""
    output_files = sorted(OUTPUT_DIR.glob("*"))
    if not output_files:
        return
    log.info("\n📁 Output files:")
    for f in output_files:
        if f.name.startswith("."):
            continue
        size_kb = f.stat().st_size / 1024
        log.info(f"   {f.name:<45} {size_kb:>8.1f} KB")


async def main():
    args = set(sys.argv[1:])

    if "--recon" in args:
        from recon import run_full_recon
        await run_full_recon()

    elif "--extract" in args:
        from api_extractor import extract_from_apis
        from ai_extractor import extract_all_pages
        await extract_from_apis()
        await extract_all_pages()

    elif "--report" in args:
        from report_generator import generate_report
        generate_report()

    else:
        await run_full_pipeline()


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                OUTPUT_DIR / f"agent_{datetime.now():%Y%m%d_%H%M%S}.log",
                encoding="utf-8",
            ),
        ],
    )
    asyncio.run(main())
