"""Configuration and constants."""
import os
import random
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ═══ STEALTH SETTINGS ═══
# Human-like delays — NEVER go below these
DELAY_BETWEEN_PAGES_MIN = 3.0      # seconds between page loads
DELAY_BETWEEN_PAGES_MAX = 7.0
DELAY_BETWEEN_ACTIONS_MIN = 1.0    # seconds between scroll/click
DELAY_BETWEEN_ACTIONS_MAX = 3.0
DELAY_BETWEEN_LEVELS = 15.0        # seconds pause between cascade levels
DELAY_SESSION_WARMUP = 5.0         # seconds on homepage before navigating

# Rate limiting protection
MAX_REQUESTS_PER_MINUTE = 8        # stay well under any rate limit
MAX_PAGES_PER_SESSION = 4          # don't hit too many pages in one session

# Detect Docker environment
IN_DOCKER = os.path.exists("/.dockerenv")

# User-Agent rotation pool (pick ONE per session, not per request)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# Warmup URL — visit before targets (looks like real browsing)
WARMUP_URL = "https://moldtelecom.md/"

# Targets in navigation order (like a real user clicking through menu)
TARGETS = {
    "mobile_subscriptions": "https://moldtelecom.md/Abonamente_Telefonie_Mobila/",
    "mobile_options": "https://moldtelecom.md/Optiuni-telefonie-mobila",
    "mobile_internet": "https://moldtelecom.md/Abonamente-Internet-mobil",
}

SITEMAP_URLS = [
    "https://moldtelecom.md/sitemap.xml",
    "https://www.moldtelecom.md/sitemap.xml",
]

# Claude Code CLI (no API key — uses OAuth from Pro/Max plan)
CLAUDE_CLI = shutil.which("claude") or "claude"
CLAUDE_MODEL = "sonnet"
CLAUDE_TIMEOUT = 120

# Quality gate thresholds
MIN_SUBSCRIPTIONS = 4
MIN_PRICE_MDL = 10
MAX_PRICE_MDL = 500

# Legacy compat settings used by level3_pydoll
PAGE_LOAD_WAIT = 4.0
SCROLL_STEPS = 5
SCROLL_DELAY = 1.0
REQUEST_DELAY_MIN = 3.0
REQUEST_DELAY_MAX = 7.0

# Output
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

SUBSCRIPTION_KEYWORDS = [
    "abonament", "tarif", "pret", "price", "subscription",
    "liberty", "star", "smart", "connect", "minute", "sms",
    "data", "internet", "MDL", "lei", "mobil",
]


def get_session_ua() -> str:
    """Pick ONE random User-Agent for this entire session."""
    return random.choice(USER_AGENTS)


def get_browser_headers() -> dict:
    """Headers that mimic a real browser visit from Moldova."""
    return {
        "User-Agent": get_session_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ro-MD,ro;q=0.9,ru;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def check_claude_cli() -> bool:
    """Check if Claude Code CLI is installed and available."""
    import subprocess
    try:
        r = subprocess.run([CLAUDE_CLI, "--version"], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
