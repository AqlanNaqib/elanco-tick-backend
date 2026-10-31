"""
Spike detection: finds months where a city had a lot more sightings than usual.

For each city I count the sightings in every month. Then for each month I look at
the 12 months before it, work out the average and how much it normally varies,
and turn that into a z-score. A high z-score means that month was unusual.
"""
from collections import Counter
from statistics import mean, stdev

from app.regions import region_for


def month_of(date):
    return f"{date.year}-{date.month:02d}"


def months_between(first, last):
    """Every month from first to last, e.g. "2023-11", "2023-12", "2024-01"."""
    year, month = int(first[:4]), int(first[5:])
    months = []
    while f"{year}-{month:02d}" <= last:
        months.append(f"{year}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def find_spikes(rows, threshold=2.0, min_count=3, window=12):
    """rows is a list of (date, city) pairs. Returns the spikes, most unusual first."""
    if not rows:
        return []

    counts = Counter((city, month_of(date)) for date, city in rows)
    all_months = months_between(min(m for _, m in counts), max(m for _, m in counts))
    cities = sorted({city for city, _ in counts})

    spikes = []
    for city in cities:
        monthly = [counts[(city, month)] for month in all_months]

        for i in range(window, len(monthly)):
            history = monthly[i - window:i]  
            usual = mean(history)
            spread = max(stdev(history), 0.5)
            z_score = (monthly[i] - usual) / spread

            if z_score >= threshold and monthly[i] >= min_count:
                spikes.append({
                    "location": city,
                    "region": region_for(city),
                    "period": all_months[i],
                    "count": monthly[i],
                    "usual": round(usual, 2),
                    "z_score": round(z_score, 2),
                })

    spikes.sort(key=lambda spike: spike["z_score"], reverse=True)
    return spikes