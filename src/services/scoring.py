"""Lead scoring engine — assigns a 0-100 quality score to each lead."""

import logging

from src.services.discovery import DiscoveredBusiness

logger = logging.getLogger(__name__)


def score_lead(
    biz: DiscoveredBusiness,
    website_type: str,
    has_contact: bool = False,
) -> int:
    """Calculate a quality score (0-100) for a lead based on multiple signals.

    Scoring breakdown:
        +30  No website at all
        +20  Social-only website (Facebook/Instagram page as "website")
        +15  No mobile app detected (reserved for Phase 2)
        +10  Has phone number (easier for sales outreach)
        +10  High rating (4.0+)
        +10  High review count (50+ reviews = active customer base)
        +5   Owner/contact name found

    Args:
        biz: The discovered business data
        website_type: "none", "social_only", or "real"
        has_contact: Whether we found an owner/contact name

    Returns:
        Integer score from 0 to 100
    """
    score = 0

    # Website presence (biggest signal)
    if website_type == "none":
        score += 30
    elif website_type == "social_only":
        score += 20

    # Phone availability
    if biz.phone:
        score += 10

    # Rating quality
    if biz.rating and biz.rating >= 4.0:
        score += 10

    # Review volume (active business)
    if biz.review_count and biz.review_count >= 50:
        score += 10

    # Contact found
    if has_contact:
        score += 5

    # Cap at 100
    score = min(score, 100)

    logger.debug(f"  Score for {biz.business_name}: {score}/100")
    return score


def determine_auto_status(score: int) -> str:
    """Determine the initial pipeline status based on the quality score.

    Args:
        score: The lead quality score (0-100)

    Returns:
        "to_contact" if score >= 50, otherwise "new"
    """
    if score >= 50:
        return "to_contact"
    return "new"
