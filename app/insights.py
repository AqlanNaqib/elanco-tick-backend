"""
Spike detection: flags months where a city had far more sightings than usual.
"""
import pandas as pd

from app.regions import region_for


def find_spikes(rows, threshold: float = 2.0, window: int = 12, min_count: int = 3) -> list[dict]:
    """rows: (date, location) pairs. Returns spikes, the most unusual first."""
    df = pd.DataFrame(rows, columns=["date", "location"])
    if df.empty:
        return []

    df["month"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).dt.to_period("M")

    counts = df.groupby(["location", "month"]).size().unstack(fill_value=0)
    all_months = pd.period_range(counts.columns.min(), counts.columns.max(), freq="M")
    counts = counts.reindex(columns=all_months, fill_value=0)

    history = counts.T.shift(1).rolling(window, min_periods=window)
    mean = history.mean().T
    
    std = history.std().T.clip(lower=0.5)
    z_scores = (counts - mean) / std

    spikes = []
    for city in counts.index:
        for month in counts.columns:
            count = int(counts.at[city, month])
            z = z_scores.at[city, month]
            if pd.notna(z) and z >= threshold and count >= min_count:
                spikes.append({
                    "location": city,
                    "region": region_for(city),
                    "period": str(month),
                    "count": count,
                    "usual": round(float(mean.at[city, month]), 2),
                    "z_score": round(float(z), 2),
                })

    return sorted(spikes, key=lambda s: s["z_score"], reverse=True)