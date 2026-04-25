"""Google Places API (New) integration for discovering businesses.

Implements grid-based scanning to bypass the 60-result-per-query cap.
Instead of one search, we divide the city into a grid of overlapping
circles and search each one, then deduplicate by place ID.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@dataclass
class DiscoveredBusiness:
    """Raw business data from the API."""
    google_place_id: str
    business_name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    website_url: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    types: list[str] = field(default_factory=list)


class DiscoveryService:
    """Discovers businesses using the official Google Places API (New).
    
    Uses grid-based scanning to find more than the 60-result API cap.
    """

    def __init__(self):
        self.api_key = settings.google_places_api_key

    async def search_wide(self, niche: str, city: str, country: str = "") -> list[DiscoveredBusiness]:
        """Search for businesses across the entire city using grid scanning.
        
        This breaks the 60-result cap by:
        1. Getting the city center coordinates
        2. Generating a grid of lat/lng points covering the city
        3. Running a search at each grid point with locationBias
        4. Deduplicating results by google_place_id
        """
        if not self.api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is not set in the environment.")

        query = f"{niche} in {city} {country}".strip()
        logger.info(f"Starting grid-based discovery: '{query}'")

        # Step 1: Get city center coordinates
        center_lat, center_lng = await self._get_city_center(city, country)
        if center_lat is None:
            # Fallback: run a single search without grid
            logger.warning("Could not geocode city center, falling back to single search.")
            return await self.search(niche, city, country)

        # Step 2: Generate grid points
        grid_points = self._generate_grid_points(
            center_lat, center_lng,
            grid_size=settings.grid_size,
            radius_meters=settings.grid_radius_meters,
        )
        logger.info(f"Generated {len(grid_points)} grid points for '{city}'")

        # Step 3: Search each grid point
        seen_ids: set[str] = set()
        seen_names: set[str] = set()
        all_businesses: list[DiscoveredBusiness] = []

        for i, (lat, lng) in enumerate(grid_points):
            logger.info(f"  Grid point {i+1}/{len(grid_points)}: ({lat:.4f}, {lng:.4f})")
            try:
                # Use ONLY the niche (e.g. "Cafes") for grid searches
                # This lets the locationRestriction find everything in that zone
                # without Google filtering for "best match in city"
                businesses = await self.search(
                    niche, "", "",  # No city/country in the niche-only query
                    location_bias_lat=lat,
                    location_bias_lng=lng,
                    location_bias_radius=settings.grid_radius_meters,
                )
                # Deduplicate by place ID AND Business Name to prevent chain spam (e.g. 50 Starbucks)
                new_count = 0
                for biz in businesses:
                    biz_name_lower = biz.name.lower().strip()
                    if biz.google_place_id not in seen_ids and biz_name_lower not in seen_names:
                        seen_ids.add(biz.google_place_id)
                        seen_names.add(biz_name_lower)
                        all_businesses.append(biz)
                        new_count += 1
                logger.info(f"    Found {len(businesses)} results, {new_count} new (total: {len(all_businesses)})")
            except Exception as e:
                logger.error(f"    Grid point search failed: {e}")
                continue

            # Small delay to respect rate limits
            await asyncio.sleep(0.2)

        logger.info(f"Grid discovery complete: {len(all_businesses)} unique businesses found across {len(grid_points)} zones.")
        return all_businesses

    async def search(
        self,
        niche: str,
        city: str,
        country: str = "",
        location_bias_lat: float | None = None,
        location_bias_lng: float | None = None,
        location_bias_radius: int | None = None,
    ) -> list[DiscoveredBusiness]:
        """Search for businesses matching the niche in the given city using Google Places."""
        
        if not self.api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is not set in the environment.")

        if city:
            query = f"{niche} in {city} {country}".strip()
        else:
            query = f"{niche}".strip()

        # Field Mask to optimize API costs (Pro-tier Essentials)
        field_mask = (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.nationalPhoneNumber,places.websiteUri,places.googleMapsUri,"
            "places.rating,places.userRatingCount,places.types,nextPageToken"
        )

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

        all_businesses: list[DiscoveredBusiness] = []
        next_page_token = ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for page in range(settings.max_pages_per_query):
                    payload: dict = {
                        "textQuery": query,
                        "pageSize": 20,  # Max allowed per page
                    }

                    # Add location bias/restriction for grid scanning
                    if location_bias_lat is not None and location_bias_lng is not None:
                        # Use locationRestriction for grid scanning to FORCE results in that area
                        # Use locationBias for general search
                        area_key = "locationRestriction" if location_bias_radius else "locationBias"
                        payload[area_key] = {
                            "circle": {
                                "center": {
                                    "latitude": location_bias_lat,
                                    "longitude": location_bias_lng,
                                },
                                "radius": location_bias_radius or 5000,
                            }
                        }

                    if next_page_token:
                        payload["pageToken"] = next_page_token

                    response = await client.post(PLACES_API_URL, json=payload, headers=headers)
                    response.raise_for_status()

                    data = response.json()
                    places = data.get("places", [])
                    
                    logger.debug(f"  Google Places returned {len(places)} results on page {page + 1}.")

                    for place in places:
                        all_businesses.append(self._parse_place(place))

                    next_page_token = data.get("nextPageToken")
                    if not next_page_token:
                        break  # No more pages available

        except Exception as e:
            logger.error(f"Google Places API error: {e}")
            raise

        return all_businesses

    async def _get_city_center(self, city: str, country: str = "") -> tuple[float | None, float | None]:
        """Get the latitude/longitude center of a city using Google Geocoding API."""
        query = f"{city} {country}".strip()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    GEOCODE_API_URL,
                    params={"address": query, "key": self.api_key},
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "OK" and data.get("results"):
                    location = data["results"][0]["geometry"]["location"]
                    lat = location["lat"]
                    lng = location["lng"]
                    logger.info(f"City center for '{query}': ({lat:.4f}, {lng:.4f})")
                    return lat, lng
                else:
                    logger.warning(f"Geocoding returned no results for: {query}")
                    return None, None

        except Exception as e:
            logger.warning(f"Geocoding API error: {e}")
            return None, None

    @staticmethod
    def _generate_grid_points(
        center_lat: float,
        center_lng: float,
        grid_size: int = 3,
        radius_meters: int = 2500,
    ) -> list[tuple[float, float]]:
        """Generate a grid of lat/lng points covering the city.
        
        For a 3×3 grid with 2500m radius, this covers roughly a 15km × 15km area,
        which is enough for most cities. The circles overlap slightly to avoid gaps.
        
        Args:
            center_lat: City center latitude
            center_lng: City center longitude
            grid_size: Number of points per side (3 = 3×3 = 9 points)
            radius_meters: Radius of each search circle in meters
        
        Returns:
            List of (lat, lng) tuples
        """
        # Spacing between grid points = 2 * radius * 0.8 (20% overlap)
        spacing_meters = radius_meters * 2 * 0.8

        # Convert meters to degrees (approximate)
        # 1 degree latitude ≈ 111,320 meters
        lat_step = spacing_meters / 111320
        # 1 degree longitude varies with latitude
        lng_step = spacing_meters / (111320 * math.cos(math.radians(center_lat)))

        points = []
        half = grid_size // 2

        for row in range(-half, half + 1):
            for col in range(-half, half + 1):
                lat = center_lat + (row * lat_step)
                lng = center_lng + (col * lng_step)
                points.append((lat, lng))

        return points

    @staticmethod
    def _parse_place(place: dict) -> DiscoveredBusiness:
        """Parse a Google Places element into our DiscoveredBusiness model."""
        location = place.get("location", {})
        display_name = place.get("displayName", {})

        return DiscoveredBusiness(
            google_place_id=place.get("id", ""),
            business_name=display_name.get("text", "Unknown"),
            address=place.get("formattedAddress"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            phone=place.get("nationalPhoneNumber"),
            website_url=place.get("websiteUri"),
            google_maps_url=place.get("googleMapsUri"),
            rating=place.get("rating"),
            review_count=place.get("userRatingCount"),
            types=place.get("types", []),
        )
