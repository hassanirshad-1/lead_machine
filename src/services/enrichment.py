"""Enrichment service — finds business owner/decision-maker info.

Two-pass enrichment:
1. Pass 1 (Serper): Search Google for owner name, email, LinkedIn URL
2. Pass 2 (Apify): Scrape LinkedIn profiles for structured owner data
"""

import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class EnrichmentResult:
    """Result of enrichment attempt for a business."""

    def __init__(
        self,
        owner_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        linkedin_url: str | None = None,
        job_title: str | None = None,
        headline: str | None = None,
        location: str | None = None,
        source: str = "none",
        confidence: float = 0.0,
    ):
        self.owner_name = owner_name
        self.email = email
        self.phone = phone
        self.linkedin_url = linkedin_url
        self.job_title = job_title
        self.headline = headline
        self.location = location
        self.source = source
        self.confidence = confidence

    @property
    def found(self) -> bool:
        return self.owner_name is not None or self.email is not None or self.linkedin_url is not None


class EnrichmentService:
    """Attempts to find owner/decision-maker information using Serper + Apify LinkedIn."""

    def __init__(self):
        self.serper_api_key = settings.serper_api_key
        self.apify_token = settings.apify_api_token

    async def enrich(
        self, business_name: str, city: str, website_url: str | None = None
    ) -> EnrichmentResult:
        """Try all available enrichment methods in priority order.
        
        Flow:
        1. Search Google (Serper) for owner info + LinkedIn URL
        2. If LinkedIn URL found → scrape profile via Apify for rich data
        3. Final attempt — targeted search for personal email if still missing
        """
        # Pass 1: Google search for owner name + LinkedIn URL
        result = await self._search_google_for_owner(business_name, city)

        # Pass 2: If we found a LinkedIn URL, scrape the profile for real data (including Email/Phone)
        if result.linkedin_url and self.apify_token:
            linkedin_data = await self._scrape_linkedin_profile(result.linkedin_url)
            if linkedin_data:
                # LinkedIn data overrides flaky regex-extracted names
                result.owner_name = linkedin_data.get("name") or result.owner_name
                result.email = linkedin_data.get("email") or result.email
                result.phone = linkedin_data.get("phone") or result.phone
                result.job_title = linkedin_data.get("job_title")
                result.headline = linkedin_data.get("headline")
                result.location = linkedin_data.get("location")
                result.source = "linkedin_apify"
                result.confidence = 0.95
                logger.info(f"  [Enrichment] LinkedIn enriched: {result.owner_name} (Email: {result.email})")

        # Pass 3: Final attempt — Targeted search for owner's personal email if still missing
        if result.owner_name and not result.email and self.serper_api_key:
            personal_email = await self._search_for_personal_email(result.owner_name, business_name)
            if personal_email:
                result.email = personal_email
                logger.info(f"  [Enrichment] Found personal email via targeted search: {personal_email}")

        if result.found:
            return result

        # Nothing found
        logger.debug(f"  No enrichment data found for: {business_name}")
        return EnrichmentResult()

    async def _search_google_for_owner(
        self, business_name: str, city: str
    ) -> EnrichmentResult:
        """Search Google (via Serper.dev) for the business owner/founder info.
        
        Runs TWO searches:
        1. General owner search: finds names, emails
        2. LinkedIn-targeted search: finds LinkedIn profile URLs directly
        """
        owner_name = None
        email = None
        phone = None
        linkedin_url = None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if not self.serper_api_key:
                    logger.debug("  Skipping Serper search: API key missing")
                    return EnrichmentResult()

                url = "https://google.serper.dev/search"
                headers = {
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json"
                }

                # --- Search 1: General owner search ---
                general_query = f'"{business_name}" owner OR founder OR CEO {city}'
                logger.debug(f"  Enrichment search 1: {general_query}")
                
                data = {"q": general_query, "num": 20}
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                general_results = response.json().get("organic", [])

                # --- Search 2: LinkedIn-targeted search ---
                linkedin_query = f'site:linkedin.com/in/ "{business_name}" owner OR founder {city}'
                logger.debug(f"  Enrichment search 2: {linkedin_query}")
                
                data = {"q": linkedin_query, "num": 10}
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                linkedin_results = response.json().get("organic", [])

                # Process LinkedIn results first (higher quality)
                for item in linkedin_results:
                    link = item.get("link", "")
                    title = item.get("title", "")

                    if "linkedin.com/in/" in link and not linkedin_url:
                        linkedin_url = link
                        logger.info(f"  [Enrichment] Found LinkedIn: {linkedin_url}")
                        
                        # LinkedIn titles are formatted as "FirstName LastName - Title | LinkedIn"
                        name_from_linkedin = self._extract_name_from_linkedin_title(title)
                        if name_from_linkedin:
                            owner_name = name_from_linkedin
                            logger.info(f"  [Enrichment] Owner from LinkedIn title: {owner_name}")
                        break

                # Process general results
                for item in general_results:
                    snippet = item.get('snippet', '')
                    title = item.get('title', '')
                    link = item.get('link', '')
                    combined_text = f"{title} {snippet}"

                    # 1. Extract Email
                    if not email:
                        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', combined_text)
                        if email_match:
                            found_email = email_match.group(0).lower()
                            # Filter out generic/noreply emails
                            if not any(noise in found_email for noise in ['noreply', 'no-reply', 'support@', 'info@', 'hello@', 'contact@']):
                                email = found_email
                                logger.info(f"  [Enrichment] Found email: {email}")

                    # 2. Extract LinkedIn (if not found in dedicated search)
                    if not linkedin_url and "linkedin.com/in/" in link:
                        linkedin_url = link
                        logger.info(f"  [Enrichment] Found LinkedIn from general: {linkedin_url}")
                        
                        name_from_linkedin = self._extract_name_from_linkedin_title(title)
                        if name_from_linkedin and not owner_name:
                            owner_name = name_from_linkedin

                    # 3. Extract Owner Name (if not found from LinkedIn)
                    if not owner_name:
                        owner_name = self._extract_owner_name(combined_text)

                if owner_name or email or linkedin_url:
                    return EnrichmentResult(
                        owner_name=owner_name,
                        email=email,
                        phone=phone,
                        linkedin_url=linkedin_url,
                        source="google_search",
                        confidence=0.8 if linkedin_url else (0.6 if owner_name else 0.4)
                    )

                return EnrichmentResult()

        except Exception as e:
            logger.warning(f"  Enrichment search failed: {e}")
            return EnrichmentResult()

    @staticmethod
    def _extract_name_from_linkedin_title(title: str) -> str | None:
        """Extract owner name from a LinkedIn search result title."""
        if not title:
            return None

        # Remove "| LinkedIn" suffix
        title = re.sub(r'\s*\|\s*LinkedIn\s*$', '', title, flags=re.IGNORECASE)
        
        # Take everything before the first " - " as the name
        parts = title.split(" - ")
        if parts:
            candidate = parts[0].strip()
            # Validate: should be 2-4 capitalized words
            words = candidate.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                return candidate

        return None

    @staticmethod
    def _extract_owner_name(text: str) -> str | None:
        """Extract owner/founder name from search snippet text."""
        patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:is the|is a)\s+(?:owner|founder|CEO|co-founder|managing director)',
            r'(?:owner|founder|CEO|co-founder)[,:]?\s+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'(?:owned by|founded by|run by|managed by)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'([A-Z][a-z]+ [A-Z][a-z]+)[,\s]+(?:owner|founder|CEO)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                noise_words = {
                    'interview', 'with', 'was', 'has', 'the', 'from',
                    'about', 'and', 'for', 'this', 'that', 'here',
                    'best', 'top', 'new', 'our', 'your', 'more',
                    'meet', 'how', 'why', 'what', 'who', 'all',
                }
                name_words = name.lower().split()
                if any(word in noise_words for word in name_words):
                    continue
                if len(name.split()) >= 2:
                    return name

        return None

    async def _scrape_linkedin_profile(self, linkedin_url: str) -> dict | None:
        """Scrape a LinkedIn profile using Apify's LinkedIn Profile Scraper."""
        if not self.apify_token:
            logger.debug("  Skipping Apify LinkedIn scrape: API token missing")
            return None

        logger.info(f"  [Enrichment] Scraping LinkedIn profile via Apify: {linkedin_url}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                actor_id = "dev_fusion~linkedin-profile-scraper"
                run_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
                
                payload = {"profileUrls": [linkedin_url]}
                
                response = await client.post(
                    run_url,
                    json=payload,
                    params={"token": self.apify_token},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                items = response.json()
                if not items or not isinstance(items, list):
                    logger.warning("  Apify returned no profile data")
                    return None

                profile = items[0]
                full_name = profile.get("fullName") or profile.get("firstName", "")
                if not full_name and profile.get("firstName"):
                    full_name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()

                headline = profile.get("headline") or profile.get("title") or profile.get("occupation")
                job_title = profile.get("occupation") or profile.get("position")
                
                if not job_title and headline:
                    title_match = re.match(r'^(.+?)(?:\s+at\s+|\s+@\s+|\s*\|\s*)', headline)
                    if title_match:
                        job_title = title_match.group(1).strip()
                    else:
                        job_title = headline.split(" - ")[0].strip() if " - " in headline else headline

                if not job_title:
                    experiences = profile.get("experience") or profile.get("experiences") or profile.get("positions", [])
                    if experiences and isinstance(experiences, list) and len(experiences) > 0:
                        job_title = experiences[0].get("title") or experiences[0].get("position")

                location = profile.get("location") or profile.get("addressLocality") or profile.get("city")
                if not location and profile.get("locationName"):
                    location = profile.get("locationName")

                # Extract Email and Phone if found by Apify
                email = profile.get("email") or profile.get("mail")
                phone = profile.get("phone") or profile.get("mobile") or profile.get("phoneNumber")

                result = {
                    "name": full_name or None,
                    "job_title": job_title,
                    "headline": headline,
                    "location": location,
                    "email": email,
                    "phone": phone,
                }

                logger.info(f"  [Enrichment] Apify result: {result}")
                return result

        except httpx.TimeoutException:
            logger.warning("  Apify LinkedIn scrape timed out (120s)")
            return None
        except Exception as e:
            logger.warning(f"  Apify LinkedIn scrape failed: {e}")
            return None

    async def _search_for_personal_email(self, owner_name: str, business_name: str) -> str | None:
        """Perform a targeted Google search for the owner's personal/business email."""
        query = f'"{owner_name}" "{business_name}" email OR contact OR "@gmail.com"'
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = "https://google.serper.dev/search"
                headers = {"X-API-KEY": self.serper_api_key, "Content-Type": "application/json"}
                data = {"q": query, "num": 5}
                
                response = await client.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    results = response.json().get("organic", [])
                    for item in results:
                        text = f"{item.get('title', '')} {item.get('snippet', '')}"
                        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                        if email_match:
                            email = email_match.group(0).lower()
                            if not any(noise in email for noise in ['noreply', 'support@']):
                                return email
            return None
        except Exception:
            return None
