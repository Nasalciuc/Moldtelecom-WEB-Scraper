"""
Report Generator — anti-scraping security assessment Markdown report.

Reads:
    output/recon_report.json
    output/sitemap_analysis.json
    output/subscriptions_validated.json

Writes:
    output/anti_scraping_report.md
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

log = logging.getLogger(__name__)

RECON_REPORT = OUTPUT_DIR / "recon_report.json"
SITEMAP_REPORT = OUTPUT_DIR / "sitemap_analysis.json"
VALIDATED_REPORT = OUTPUT_DIR / "subscriptions_validated.json"
MD_REPORT = OUTPUT_DIR / "anti_scraping_report.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning(f"Could not parse {path.name}: {e}")
    return {}


def _severity(score: int) -> str:
    if score >= 8:
        return "🔴 RIDICATĂ"
    if score >= 5:
        return "🟡 MEDIE"
    return "🟢 SCĂZUTĂ"


def _grade(score: int) -> str:
    if score >= 8:
        return "Critică"
    if score >= 6:
        return "Ridicată"
    if score >= 4:
        return "Medie"
    return "Scăzută"


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _compute_scores(recon: dict, sitemap: dict, validated: dict) -> dict:
    # Sitemap score
    total_urls = sitemap.get("total_urls_discovered", 0)
    if total_urls > 50:
        sitemap_score = 8
    elif total_urls > 0:
        sitemap_score = 5
    else:
        sitemap_score = 2

    # API score
    endpoints_found = 0
    all_anti_scraping: list[str] = []
    recon_results = recon.get("results", {})
    for _name, info in recon_results.items():
        endpoints_found += info.get("api_endpoints_found", 0)
        all_anti_scraping.extend(info.get("anti_scraping", []))

    api_score = min(9, endpoints_found + 3)

    # Automation (browser detection) score
    automation_score = 9 if not all_anti_scraping else 5

    # AI extraction score — always 10 (AI can always read rendered HTML)
    ai_score = 10

    return {
        "sitemap": sitemap_score,
        "api": api_score,
        "automation": automation_score,
        "ai": ai_score,
        "anti_scraping_signals": list(set(all_anti_scraping)),
        "endpoints_found": endpoints_found,
    }


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def _endpoints_table(recon: dict) -> str:
    rows: list[str] = []
    for target_name, info in recon.get("results", {}).items():
        for ep in info.get("endpoints", []):
            url = ep.get("url", "")[:80]
            ct = ep.get("content_type", "")
            status = ep.get("status_code", "?")
            has_data = "✅" if ep.get("contains_subscription_data") else "—"
            rows.append(f"| `{url}` | {ct} | {status} | {has_data} |")

    if not rows:
        return "_Nu au fost descoperite API endpoints._\n"

    header = (
        "| URL | Content-Type | Status | Date abonamente |\n"
        "|-----|-------------|--------|----------------|\n"
    )
    return header + "\n".join(rows) + "\n"


def _subscriptions_table(validated: dict) -> str:
    subs = validated.get("subscriptions", [])
    if not subs:
        return "_Nu au fost extrase abonamente._\n"

    rows: list[str] = []
    for s in subs:
        name = s.get("name", "—")
        price = s.get("price_mdl", "—")
        promo = s.get("price_promo_mdl") or "—"
        minutes = s.get("minutes_in_network", "—")
        nat = s.get("minutes_national", "—")
        sms = s.get("sms_in_network", "—")
        data = s.get("data_gb", "—")
        confidence = s.get("confidence", "—")
        rows.append(
            f"| {name} | {price} MDL | {promo} | {minutes} | {nat} | {sms} | {data} | {confidence} |"
        )

    header = (
        "| Nume | Preț MDL | Preț Promo | Minute rețea | Min. naționale | SMS | Internet | Confidence |\n"
        "|------|----------|-----------|-------------|----------------|-----|----------|------------|\n"
    )
    return header + "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def _executive_summary(scores: dict, sitemap: dict, validated: dict) -> str:
    total_urls = sitemap.get("total_urls_discovered", 0)
    sub_count = len(validated.get("subscriptions", []))
    endpoints = scores["endpoints_found"]
    signals = scores["anti_scraping_signals"]
    protection = "fără protecții anti-bot detectate" if not signals else f"cu semnale: {', '.join(signals)}"

    vuln_level = "RIDICAT" if scores['api'] >= 7 else "MEDIU"
    return (
        f"Analiza site-ului moldtelecom.md a identificat **{total_urls} URL-uri** în sitemap, "
        f"**{endpoints} API endpoints** expuse și a extras cu succes **{sub_count} planuri de abonament** "
        f"— {protection}. "
        f"Nivelul general de vulnerabilitate la scraping automat este **{vuln_level}**, "
        f"recomandând implementarea urgentă a rate limiting și WAF."
    )


# ---------------------------------------------------------------------------
# Main report function
# ---------------------------------------------------------------------------

def generate_report() -> Path:
    """
    Generate Markdown anti-scraping security report.
    Returns path to generated file.
    """
    log.info("📊 Generating anti-scraping report...")

    recon = _load_json(RECON_REPORT)
    sitemap = _load_json(SITEMAP_REPORT)
    validated = _load_json(VALIDATED_REPORT)

    scores = _compute_scores(recon, sitemap, validated)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Recon stats
    recon_results = recon.get("results", {})
    total_requests = sum(r.get("total_requests", 0) for r in recon_results.values())
    total_endpoints = scores["endpoints_found"]
    sub_endpoints = sum(
        1 for info in recon_results.values()
        for ep in info.get("endpoints", [])
        if ep.get("contains_subscription_data")
    )

    # Anti-scraping signals across all pages
    signals = scores["anti_scraping_signals"]
    pydoll_detected = "detectat" if "webdriver_check" in signals else "nedetectat"

    # Sitemap stats
    total_urls = sitemap.get("total_urls_discovered", 0)
    cat_counts = sitemap.get("category_counts", {})
    mobile_urls = cat_counts.get("mobile_subscriptions", 0)

    # Validated subs
    sub_count = len(validated.get("subscriptions", []))
    primary_method = "api_direct" if any(
        s.get("source_method") == "api_direct"
        for s in validated.get("subscriptions", [])
    ) else "ai_claude"
    confidence_levels = [s.get("confidence", "low") for s in validated.get("subscriptions", [])]
    overall_confidence = (
        "high" if all(c == "high" for c in confidence_levels) and confidence_levels
        else "medium" if confidence_levels
        else "low"
    )

    report_lines: list[str] = [
        "# 🛡️ Moldtelecom Anti-Scraping Security Assessment",
        "",
        f"**Data:** {now}  ",
        "**Agent:** Moldtelecom AI Scraping Agent v1.0  ",
        "**Confidențialitate:** Uz intern — Security Assessment  ",
        "",
        "---",
        "",
        "## Rezumat Executiv",
        "",
        _executive_summary(scores, sitemap, validated),
        "",
        "---",
        "",
        "## Vectori de Atac Testați",
        "",
        "### 1. Analiza Sitemap",
        "",
        f"- **Total URL-uri descoperite:** {total_urls}",
        f"- **URL-uri telefonie mobilă:** {mobile_urls}",
        f"- **Vulnerabilitate:** {_severity(scores['sitemap'])}",
        "- **Recomandare:** Restricționați accesul la sitemap sau adăugați rate-limiting pe endpoint.",
        "",
    ]

    # Sitemap category breakdown
    if cat_counts:
        report_lines += [
            "**Distribuție pe categorii:**",
            "",
            "| Categorie | URL-uri |",
            "|-----------|---------|",
        ]
        for cat, cnt in cat_counts.items():
            report_lines.append(f"| {cat.replace('_', ' ').title()} | {cnt} |")
        report_lines.append("")

    report_lines += [
        "### 2. Network Interception (API Endpoints)",
        "",
        f"- **Total requests interceptate:** {total_requests}",
        f"- **API endpoints descoperite:** {total_endpoints}",
        f"- **Endpoints cu date de abonamente:** {sub_endpoints}",
        f"- **Vulnerabilitate:** {_severity(scores['api'])}",
        "- **Recomandare:** Implementați autentificare token pe API-urile interne. "
          "Adăugați CORS headers restrictive și rate-limiting per IP.",
        "",
        "**Endpoints descoperite:**",
        "",
        _endpoints_table(recon),
        "### 3. Browser Automation Detection",
        "",
        f"- **Pydoll (CDP stealth):** {pydoll_detected}",
        f"- **Anti-scraping signals detectate:** {', '.join(signals) if signals else 'niciunul'}",
        f"- **Vulnerabilitate:** {_severity(scores['automation'])}",
        "- **Recomandare:** Implementați browser fingerprinting (TLS JA3, canvas, WebGL) "
          "și integrați Cloudflare Bot Management sau similar.",
        "",
        "### 4. AI Data Extraction",
        "",
        f"- **Abonamente extrase:** {sub_count}",
        f"- **Metoda primară:** {primary_method}",
        f"- **Confidence:** {overall_confidence}",
        "- **Vulnerabilitate:** 🔴 RIDICATĂ (AI poate extrage date din orice HTML randat)",
        "- **Recomandare:** Server-Side Rendering condiționat (CAPTCHA pentru prețuri), "
          "watermarking date, monitorizare pattern-uri de acces.",
        "",
        "---",
        "",
        "## Date Extrase — Abonamente Telefonie Mobilă",
        "",
        _subscriptions_table(validated),
        "",
        "---",
        "",
        "## Scor de Vulnerabilitate",
        "",
        "| Vector | Scor (1-10) | Gravitate |",
        "|--------|-------------|-----------|",
        f"| Sitemap expus | {scores['sitemap']}/10 | {_grade(scores['sitemap'])} |",
        f"| API neprotejate | {scores['api']}/10 | {_grade(scores['api'])} |",
        f"| Browser automation bypass | {scores['automation']}/10 | {_grade(scores['automation'])} |",
        f"| AI extraction | {scores['ai']}/10 | Critică |",
        "",
        f"**Scor mediu: {(scores['sitemap'] + scores['api'] + scores['automation'] + scores['ai']) / 4:.1f}/10**",
        "",
        "---",
        "",
        "## Recomandări Prioritare",
        "",
        "### Urgente (1 săptămână)",
        "1. **Rate limiting** pe toate API endpoints interne (max 10 req/min per IP)",
        "2. **CORS headers** restrictive — permiteți doar originea `moldtelecom.md`",
        "3. **robots.txt** actualizat pentru a descuraja crawlere",
        "",
        "### Pe termen scurt (1 lună)",
        "4. **WAF** (Cloudflare sau similar) cu reguli anti-bot activate",
        "5. **Browser fingerprinting** avansat (TLS fingerprint, canvas, WebGL)",
        "6. **Token-based API access** — toate request-urile interne necesită JWT",
        "",
        "### Pe termen lung (3 luni)",
        "7. **Server-Side Rendering** pentru prețuri (elimină extracția din HTML)",
        "8. **Data watermarking** — prețuri ușor variate per sesiune pentru identificare",
        "9. **Monitoring activ** al pattern-urilor de acces anormale",
        "",
        "---",
        "",
        "*Raport generat automat de Moldtelecom AI Scraping Agent*  ",
        f"*{now}*",
    ]

    report_content = "\n".join(report_lines)
    MD_REPORT.write_text(report_content, encoding="utf-8")
    log.info(f"  📄 Report saved: {MD_REPORT} ({len(report_content):,} chars)")

    return MD_REPORT


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    generate_report()
