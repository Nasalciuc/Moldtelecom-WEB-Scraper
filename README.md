# Moldtelecom Subscription Scraper — 4-Level Stealth Cascade

Security assessment tool for moldtelecom.md.
Extracts mobile subscription data through a multi-level bypass cascade where each level defeats a different protection layer.

---

## What is this?

An automated agent that scrapes Moldtelecom mobile subscription plans using a 4-level cascade:

1. **Level 1 — Plain HTTP** (aiohttp): fast probe to check if pages are SPA-blocked
2. **Level 2 — Scrapling Stealth** (Scrapling StealthyFetcher): bypasses Cloudflare and fingerprint checks
3. **Level 3 — Pydoll CDP** (Chrome DevTools Protocol): full browser with network interception, catches XHR/API endpoints
4. **Level 4 — AI Extraction** (Claude Code CLI): reads raw HTML and extracts structured data via LLM

Each level has a **quality gate** — if the current level produces enough valid subscriptions, the cascade stops early. No unnecessary traffic.

---

## How it works

```
Level 1: HTTP probe (aiohttp)
    │ quality gate: got subscriptions? → done
    ▼
Level 2: Scrapling stealth fetch
    │ quality gate: got subscriptions? → done
    ▼
Level 3: Pydoll CDP browser + API interception
    │ quality gate: got subscriptions? → done
    ▼
Level 4: Claude AI extraction from best HTML
    │
    ▼
Validator → merges all sources, deduplicates
    │
    ▼
Report Generator → anti_scraping_report.md
```

**Stealth rules enforced at every level:**
- Random delays between actions (1–3s) and between pages (3–7s)
- Single User-Agent per session (rotated between sessions)
- Homepage warmup before target pages
- Human-like scroll patterns in browser levels
- Max 8 requests/minute, max 4 pages/session

---

## Prerequisites

- Python 3.10+
- Chrome/Chromium (for Level 3 Pydoll)
- Node.js + npm (for Claude Code CLI)
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code && claude login`

> **Note:** Claude CLI uses your Pro/Max plan — no API key needed.
> Without it, Level 4 degrades to regex fallback.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Setup Scrapling stealth browsers (one-time)
python -c "import scrapling; scrapling.setup()"

# Run the full 4-level cascade
cd src && python agent.py
```

---

## Graceful degradation

| Missing tool | Effect |
|---|---|
| Scrapling not installed | Level 2 skipped, cascade goes L1 → L3 → L4 |
| Pydoll not installed | Level 3 skipped, no API interception |
| Claude CLI not found | Level 4 uses regex fallback |
| Chrome not installed | Levels 2 & 3 skipped |

The agent always produces results — even if only Level 1 + regex works.

---

## Run specific levels

```bash
# Full cascade (default)
python src/agent.py

# Only run up to level N
python src/agent.py --level 1    # HTTP probe only
python src/agent.py --level 2    # HTTP + Scrapling
python src/agent.py --level 3    # HTTP + Scrapling + Pydoll

# Only validation (requires previous level outputs)
python src/agent.py --validate

# Only report generation
python src/agent.py --report

# Bash wrapper (Linux/macOS)
bash run.sh
```

---

## Docker

```bash
# Build
make build

# Login to Claude CLI (one-time)
make login

# Run full cascade
make run

# Run specific level
make level1
make level2
make level3

# Debug shell
make shell

# Clean output
make clean
```

---

## Output files

| File | Description |
|------|-------------|
| `output/level1_*.html` | Raw HTTP responses |
| `output/level1_http_probe.json` | Level 1 probe results |
| `output/level2_*.html` | Scrapling-rendered pages |
| `output/level2_scrapling_report.json` | Level 2 extraction results |
| `output/level3_pydoll_*.html` | CDP-rendered pages |
| `output/level3_pydoll_report.json` | Level 3 recon results |
| `output/level3_api_endpoints.json` | Discovered API endpoints |
| `output/level3_api_replay.json` | API replay extraction |
| `output/level4_ai_extraction.json` | Claude AI extraction |
| `output/subscriptions_final.json` | Validated & merged subscriptions |
| `output/anti_scraping_report.md` | Final security assessment report |

---

## Tech stack

| Component | Technology |
|-----------|------------|
| Level 1 HTTP | [aiohttp](https://docs.aiohttp.org/) |
| Level 2 Stealth | [Scrapling](https://github.com/AhmedAlaa612/scrapling) (StealthyFetcher) |
| Level 3 CDP | [Pydoll](https://github.com/thalissonvs/pydoll) (Chrome DevTools Protocol) |
| Level 4 AI | [Claude Code CLI](https://github.com/anthropics/claude-code) |
| Validation | Cross-source merge + deduplication |
| Runtime | Python asyncio |

---

## Disclaimer

This tool is intended exclusively for **internal security assessment**.
Use responsibly and only with authorization.
