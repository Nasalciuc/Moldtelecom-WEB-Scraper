"""Data models for Moldtelecom scraping agent."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Subscription:
    """A mobile subscription plan from Moldtelecom."""
    name: str = ""                           # e.g. "Liberty 190", "Star 150"
    price_mdl: float = 0.0                   # monthly price in MDL
    price_promo_mdl: Optional[float] = None  # promotional price if any
    minutes_in_network: str = ""             # e.g. "Nelimitat" or "300"
    minutes_national: str = ""               # minutes to other operators
    minutes_international: str = ""          # e.g. "50 min"
    sms_in_network: str = ""                 # e.g. "Nelimitat"
    data_gb: str = ""                        # e.g. "15 GB" or "Nelimitat"
    extra_features: list = field(default_factory=list)  # ["CLIP", "Roaming EU"]
    contract_months: int = 0                 # minimum contract period
    promo_conditions: str = ""               # promo terms if applicable
    source_url: str = ""
    source_method: str = ""                  # "api_direct" | "ai_extraction" | "regex_fallback"
    extracted_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiscoveredEndpoint:
    """An API endpoint discovered via network interception."""
    url: str = ""
    method: str = "GET"
    content_type: str = ""
    status_code: int = 0
    response_size_bytes: int = 0
    contains_subscription_data: bool = False
    sample_response_preview: str = ""  # first 2000 chars

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReconResult:
    """Result of reconnaissance on a single page."""
    target_name: str = ""
    target_url: str = ""
    rendered_html: str = ""           # full HTML after JS execution
    page_title: str = ""
    discovered_endpoints: list = field(default_factory=list)  # list of DiscoveredEndpoint dicts
    all_network_requests: list = field(default_factory=list)  # list of dicts
    anti_scraping_signals: list = field(default_factory=list)  # detected protections
    duration_seconds: float = 0.0
    error: str = ""
    success: bool = False


@dataclass
class ExtractionResult:
    """Result of data extraction (AI or API)."""
    method: str = ""            # "api_direct" | "ai_claude" | "regex_fallback"
    subscriptions: list = field(default_factory=list)  # list of Subscription dicts
    confidence: str = "high"    # "high" | "medium" | "low"
    error: str = ""
    duration_seconds: float = 0.0
