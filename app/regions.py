"""Maps each city in the dataset to its region."""

CITY_TO_REGION = {
    "London": "London",
    "Birmingham": "West Midlands",
    "Leicester": "East Midlands",
    "Nottingham": "East Midlands",
    "Manchester": "North West",
    "Liverpool": "North West",
    "Leeds": "Yorkshire and the Humber",
    "Sheffield": "Yorkshire and the Humber",
    "Newcastle": "North East",
    "Bristol": "South West",
    "Southampton": "South East",
    "Cardiff": "Wales",
    "Edinburgh": "Scotland",
    "Glasgow": "Scotland",
}


def region_for(city: str) -> str:
    return CITY_TO_REGION.get(city, "Unknown")