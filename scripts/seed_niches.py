"""Seed script — pre-populate niche + city combos for easy campaign creation."""

# Major cities across target markets
CITIES = {
    "US": [
        "New York", "Los Angeles", "Chicago", "Houston", "Miami",
        "Phoenix", "San Diego", "Dallas", "San Francisco", "Austin",
    ],
    "UK": [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
        "Liverpool", "Bristol", "Edinburgh", "Sheffield", "Leicester",
    ],
    "CA": [
        "Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa",
        "Edmonton", "Winnipeg", "Halifax", "Victoria", "Hamilton",
    ],
}

# Business niches that typically lack apps/websites
NICHES = [
    "Cafes",
    "Restaurants",
    "Gyms",
    "Salons",
    "Barbershops",
    "Spas",
    "Bakeries",
    "Pet Stores",
    "Florists",
    "Car Washes",
    "Dental Clinics",
    "Laundry Services",
]


def generate_campaign_combos(
    countries: list[str] | None = None,
    niches: list[str] | None = None,
    max_cities_per_country: int = 5,
) -> list[dict]:
    """Generate campaign combos from niches × cities.

    Args:
        countries: Which countries to include (default: all)
        niches: Which niches to include (default: all)
        max_cities_per_country: Limit cities per country

    Returns:
        List of dicts with keys: name, niche, city, country
    """
    selected_countries = countries or list(CITIES.keys())
    selected_niches = niches or NICHES
    combos = []

    for country in selected_countries:
        cities = CITIES.get(country, [])[:max_cities_per_country]
        for city in cities:
            for niche in selected_niches:
                combos.append({
                    "name": f"{city} {niche}",
                    "niche": niche,
                    "city": city,
                    "country": country,
                })

    return combos


if __name__ == "__main__":
    # Quick preview
    combos = generate_campaign_combos(max_cities_per_country=3)
    print(f"Generated {len(combos)} campaign combos:\n")
    for c in combos[:15]:
        print(f"  {c['name']:30s} | {c['niche']:20s} | {c['city']}, {c['country']}")
    if len(combos) > 15:
        print(f"  ... and {len(combos) - 15} more")
