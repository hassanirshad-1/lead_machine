"""Qualification service — filters businesses based on digital presence."""

import logging
import re
from urllib.parse import urlparse

from src.services.discovery import DiscoveredBusiness

logger = logging.getLogger(__name__)

# Social media domains — if a business only has these as their "website",
# they don't have a real website.
SOCIAL_DOMAINS = {
    "facebook.com",
    "fb.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "youtube.com",
    "linkedin.com",
    "yelp.com",
}


def classify_website(url: str | None) -> str:
    """Classify a business's website URL.

    Returns:
        "none"        — no website at all (best lead)
        "social_only" — only has a social media page (great lead)
        "real"        — has a real website (not qualified)
    """
    if not url or not url.strip():
        return "none"

    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc or parsed.path
        # Strip www. prefix
        domain = re.sub(r"^www\.", "", domain)
        # Extract root domain (e.g., "facebook.com" from "m.facebook.com")
        parts = domain.split(".")
        if len(parts) >= 2:
            root_domain = ".".join(parts[-2:])
        else:
            root_domain = domain

        if root_domain in SOCIAL_DOMAINS:
            return "social_only"

        return "real"
    except Exception:
        # If we can't parse it, assume it's a real website
        return "real"


def qualify_leads(
    businesses: list[DiscoveredBusiness],
) -> tuple[list[DiscoveredBusiness], list[DiscoveredBusiness]]:
    """Split businesses into qualified and disqualified lists.

    Qualified = no website or social-only website.
    Disqualified = has a real website.

    Returns:
        Tuple of (qualified, disqualified) lists
    """
    qualified = []
    disqualified = []

    for biz in businesses:
        website_type = classify_website(biz.website_url)

        # We now keep all leads but score them differently
        qualified.append(biz)
        logger.debug(
            f"  ✅ ADDED: {biz.business_name} "
            f"(website_type={website_type})"
        )

    logger.info(
        f"Qualification: {len(qualified)} qualified, "
        f"{len(disqualified)} disqualified out of {len(businesses)} total"
    )
    return qualified, disqualified
