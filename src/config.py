"""Configuration and constants."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Target URLs
TARGETS = {
    "mobile_subscriptions": "https://moldtelecom.md/Abonamente_Telefonie_Mobila/",
    "mobile_options": "https://moldtelecom.md/Optiuni-telefonie-mobila",
    "mobile_internet": "https://moldtelecom.md/Abonamente-Internet-mobil",
}

SITEMAP_URLS = [
    "https://moldtelecom.md/sitemap.xml",
    "https://www.moldtelecom.md/sitemap.xml",
]

# Scraping settings
REQUEST_DELAY_MIN = 1.5  # seconds
REQUEST_DELAY_MAX = 3.0
PAGE_LOAD_WAIT = 4.0     # extra wait after networkidle
SCROLL_STEPS = 5         # number of scroll steps for lazy loading
SCROLL_DELAY = 1.0       # delay between scrolls

# Browser headers for direct API calls
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ro-MD,ro;q=0.9,ru;q=0.8,en;q=0.7",
    "Referer": "https://moldtelecom.md/",
    "Origin": "https://moldtelecom.md",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Paths
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Keywords that indicate subscription/tariff data in URLs or content
SUBSCRIPTION_KEYWORDS = [
    "abonament", "tarif", "pret", "price", "subscription",
    "liberty", "star", "smart", "connect", "minute", "sms",
    "data", "internet", "MDL", "lei", "mobil",
]
