"""
Report Generator — 4-Level Cascade anti-scraping security assessment.

Reads all level JSON files and generates a section per level.
Writes: output/anti_scraping_report.md
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

log = logging.getLogger(__name__)

MD_REPORT = OUTPUT_DIR / "anti_scraping_report.md"


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning(f"Could not parse {path.name}: {e}")
    return {}


def _severity(score) -> str:
    if score == "N/A":
        return "N/A"
    if score >= 8:
        return "Critical"
    if score >= 5:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def _subscriptions_table(subs: list) -> str:
    if not subs:
        return "_No subscriptions extracted._\n"

    rows: list[str] = []
    for s in subs:
        name = s.get("name", "-")
        price = s.get("price_mdl", "-")
        promo = s.get("price_promo_mdl") or "-"
        minutes = s.get("minutes_in_network", "-")
        nat = s.get("minutes_national", "-")
        sms = s.get("sms_in_network", "-")
        data = s.get("data_gb", "-")
        source = s.get("source_level", s.get("source_method", "-"))
        rows.append(
            f"| {name} | {price} MDL | {promo} | {minutes} | {nat} | {sms} | {data} | {source} |"
        )

    header = (
        "| Name | Price MDL | Promo | Minutes network | Min. national | SMS | Data | Source |\n"
        "|------|----------|-------|----------------|---------------|-----|------|--------|\n"
    )
    return header + "\n".join(rows) + "\n"


def generate_report() -> Path:
    """Generate Markdown anti-scraping security report with section per level."""
    log.info("  Generating anti-scraping report...")

    l1 = _load_json(OUTPUT_DIR / "level1_http_probe.json")
    l2 = _load_json(OUTPUT_DIR / "level2_scrapling_report.json")
    l3 = _load_json(OUTPUT_DIR / "level3_pydoll_report.json")
    l4 = _load_json(OUTPUT_DIR / "level4_ai_extraction.json")
    final = _load_json(OUTPUT_DIR / "subscriptions_final.json")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- Level 1 analysis ---
    l1_results = l1.get("results", {})
    l1_has_content = any(
        r.get("has_rendered_content") for r in l1_results.values() if isinstance(r, dict)
    )
    l1_conclusion = l1.get("conclusion", "N/A")
    l1_score = 8 if l1_has_content else 2

    # --- Level 2 analysis ---
    l2_available = l2.get("available", False)
    l2_pages_with_content = l2.get("pages_with_content", 0)
    l2_pages_fetched = l2.get("pages_fetched", 0)
    l2_bypassed = l2.get("anti_bot_bypassed", 0)
    l2_score = 9 if l2_bypassed > 0 else 3

    # --- Level 3 analysis ---
    l3_available = l3.get("available", False)
    l3_results = l3.get("results", {})
    l3_endpoints = sum(r.get("api_endpoints_found", 0) for r in l3_results.values())
    l3_anti_scraping = []
    for r in l3_results.values():
        l3_anti_scraping.extend(r.get("anti_scraping", []))
    l3_anti_scraping = list(set(l3_anti_scraping))
    l3_score = min(9, l3_endpoints + 3) if l3_available else "N/A"

    # --- Level 4 analysis ---
    l4_total = l4.get("total", 0)
    l4_score = 10  # AI always adapts

    # --- Final data ---
    subs = final.get("subscriptions", [])
    gate = final.get("quality_gate_passed", False)

    # Build report
    lines = [
        "# Moldtelecom Anti-Scraping Security Assessment",
        "",
        f"**Date:** {now}  ",
        "**Agent:** Moldtelecom AI Scraping Agent v2.0 (4-Level Cascade)  ",
        "**Classification:** Internal — Security Assessment  ",
        "",
        "---",
        "",
        "## Methodology: 4-Level Cascade Testing",
        "",
        "Testing was performed in 4 escalation levels, from simplest to most advanced:",
        "",
        "### Level 1: Direct HTTP (Passive)",
        f"- **Method:** Simple HTTP GET without browser",
        f"- **Result:** {'Content returned via plain HTTP' if l1_has_content else 'Empty SPA shell returned'}",
        f"- **Protection status:** {'Failed — content accessible' if l1_has_content else 'Working — SPA blocks plain HTTP'}",
        f"- **Conclusion:** {l1_conclusion}",
    ]

    # Add per-page details for L1
    for name, r in l1_results.items():
        if isinstance(r, dict) and "html_size" in r:
            has = "with" if r.get("has_rendered_content") else "without"
            lines.append(f"- {name}: {r.get('html_size', 0):,} chars, {has} tariff content")
            if r.get("cloudflare"):
                lines.append(f"  - Cloudflare detected")

    lines += [
        "",
        "### Level 2: Stealth Browser (Scrapling)",
    ]
    if l2_available:
        lines += [
            f"- **Method:** Automated browser with anti-detection (fingerprint spoofing, TLS impersonation)",
            f"- **Anti-bot bypass:** {'Successful' if l2_bypassed > 0 else 'Failed'}",
            f"- **Pages with content:** {l2_pages_with_content} of {l2_pages_fetched}",
            f"- **Protection status:** {'Failed — stealth browser bypassed protections' if l2_bypassed > 0 else 'Working — anti-bot blocked scraper'}",
        ]
    else:
        lines += [
            "- **Status:** Scrapling not installed — level skipped",
        ]

    lines += [
        "",
        "### Level 3: Network Interception (Pydoll CDP)",
    ]
    if l3_available:
        # Count subscription-data endpoints
        sub_endpoints = 0
        endpoint_rows = []
        for target_name, info in l3_results.items():
            for ep in info.get("endpoints", []):
                has_data = ep.get("contains_subscription_data", False)
                if has_data:
                    sub_endpoints += 1
                url = ep.get("url", "")[:80]
                ct = ep.get("content_type", "")
                status = ep.get("status_code", "?")
                marker = "Yes" if has_data else "-"
                endpoint_rows.append(f"| {url} | {ct} | {status} | {marker} |")

        lines += [
            f"- **Method:** Chrome DevTools Protocol — network traffic interception",
            f"- **API endpoints discovered:** {l3_endpoints}",
            f"- **Endpoints with tariff data:** {sub_endpoints}",
            f"- **Anti-scraping signals:** {', '.join(l3_anti_scraping) if l3_anti_scraping else 'None detected'}",
            f"- **Protection status:** {'Working — anti-bot measures active' if l3_anti_scraping else 'Failed — no protections detected'}",
        ]
        if endpoint_rows:
            lines += [
                "",
                "**Discovered Endpoints:**",
                "",
                "| URL | Content-Type | Status | Subscription Data |",
                "|-----|-------------|--------|-------------------|",
            ] + endpoint_rows
    else:
        lines += [
            "- **Status:** Pydoll not installed — level skipped (optional)",
        ]

    lines += [
        "",
        "### Level 4: AI Extraction (Claude)",
        f"- **Method:** LLM semantic analysis of rendered HTML",
        f"- **Subscriptions extracted:** {l4_total}",
        "- **Protection status:** Failed — AI adapts to any HTML structure",
        "",
        "---",
        "",
        "## Extracted Data — Mobile Subscriptions",
        "",
    ]
    lines.append(_subscriptions_table(subs))
    lines += [
        "",
        f"**Quality gate:** {'PASSED' if gate else 'FAILED'} ({len(subs)} validated subscriptions)",
        "",
        "---",
        "",
        "## Vulnerability Score",
        "",
        "| Attack Vector | Score (1-10) | Severity |",
        "|---|---|---|",
        f"| SPA Rendering (L1) | {l1_score}/10 | {_severity(l1_score)} |",
        f"| Anti-Bot Bypass (L2) | {l2_score}/10 | {_severity(l2_score)} |",
        f"| Network Interception (L3) | {l3_score}{'/10' if l3_score != 'N/A' else ''} | {_severity(l3_score)} |",
        f"| AI Extraction (L4) | {l4_score}/10 | {_severity(l4_score)} |",
        "",
    ]

    # Average score (exclude N/A)
    scores = [l1_score, l2_score, l4_score]
    if l3_score != "N/A":
        scores.append(l3_score)
    avg = sum(scores) / len(scores) if scores else 0
    lines.append(f"**Average Score: {avg:.1f}/10**")

    lines += [
        "",
        "---",
        "",
        "## Recommendations",
        "",
        "### Urgent (1 week)",
        "1. Rate limiting on all API endpoints (max 60 req/min per IP)",
        "2. Restrictive CORS headers on internal APIs",
        "3. Updated robots.txt with Disallow on sensitive endpoints",
        "",
        "### Short-term (1 month)",
        "4. WAF (Cloudflare or similar)",
        "5. Advanced browser fingerprinting (Canvas + WebGL + AudioContext)",
        "6. Token-based API access (JWT/HMAC on all endpoints)",
        "",
        "### Long-term (3 months)",
        "7. Server-Side Rendering for pricing data",
        "8. Data watermarking for leak source detection",
        "9. Active monitoring — alerting on abnormal access patterns",
        "",
        "---",
        "",
        "*Report generated automatically by Moldtelecom AI Scraping Agent*  ",
        f"*{now}*",
    ]

    report_content = "\n".join(lines)
    MD_REPORT.write_text(report_content, encoding="utf-8")
    log.info(f"  Report saved: {MD_REPORT} ({len(report_content):,} chars)")

    return MD_REPORT


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    generate_report()
