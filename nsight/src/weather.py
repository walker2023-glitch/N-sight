"""
weather.py — Precipitation index lookup for N-SIGHT.

Rules:
- No st.* imports or calls anywhere in this file.
- Never raises. All failures return precip_index=1.0 with error key populated.
- Uses geopy (Nominatim) for geocoding and meteostat (Monthly) for climate data.
"""

from __future__ import annotations

import datetime

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from meteostat import Point, Monthly

from src.constants import METEOSTAT_LOOKBACK_YEARS, PRECIP_INDEX_BASELINE_MM


# Nominatim requires a non-empty, descriptive user_agent per OSM policy.
_GEOCODER = Nominatim(user_agent="nsight_ag_app_v1")

# Meteostat monthly data column that holds precipitation totals (mm).
_PRECIP_COL = "prcp"


def _fallback(error_message: str) -> dict:
    """Return a safe fallback result dict with precip_index=1.0."""
    return {
        "precip_index": 1.0,
        "mean_annual_mm": None,
        "station_name": None,
        "lat": None,
        "lon": None,
        "years_used": 0,
        "error": error_message,
    }


def get_precipitation_index(location_str: str) -> dict:
    """
    Resolve a location string to a precipitation index relative to 450 mm/year.

    Steps (§6):
      1. Geocode location_str → (lat, lon) via Nominatim.
      2. Fetch meteostat Monthly records for the past METEOSTAT_LOOKBACK_YEARS years.
      3. Aggregate monthly totals into mean annual precipitation (mm).
      4. precip_index = mean_annual_mm / PRECIP_INDEX_BASELINE_MM

    Returns:
      {
        "precip_index":   float,        # 1.0 on failure
        "mean_annual_mm": float | None,
        "station_name":   str | None,   # best-match station name from meteostat
        "lat":            float | None,
        "lon":            float | None,
        "years_used":     int,          # calendar years with usable data
        "error":          str | None,   # None on success
      }

    Never raises — any exception is caught and returned as error=<message>.
    """
    try:
        # ── Step 1: Geocode ───────────────────────────────────────────────────
        try:
            location = _GEOCODER.geocode(location_str, timeout=10)
        except (GeocoderTimedOut, GeocoderServiceError) as geo_exc:
            return _fallback(f"Geocoding service error for '{location_str}': {geo_exc}")

        if location is None:
            return _fallback(
                f"Location '{location_str}' could not be found. "
                "Try a city name, ZIP code, or 'City, State' format."
            )

        lat = location.latitude
        lon = location.longitude

        # ── Step 2: Build date range ──────────────────────────────────────────
        end_date   = datetime.datetime.now()
        start_date = datetime.datetime(end_date.year - METEOSTAT_LOOKBACK_YEARS, 1, 1)
        end_date   = datetime.datetime(end_date.year - 1, 12, 31)  # full calendar years only

        # ── Step 3: Fetch monthly climate data ────────────────────────────────
        point = Point(lat, lon)
        monthly_data = Monthly(point, start_date, end_date)
        df = monthly_data.fetch()

        if df is None or df.empty or _PRECIP_COL not in df.columns:
            return _fallback(
                f"No precipitation data found near '{location_str}' "
                f"({lat:.4f}, {lon:.4f}). Station coverage may be insufficient."
            )

        precip_series = df[_PRECIP_COL].dropna()
        if precip_series.empty:
            return _fallback(
                f"Precipitation column exists but contains no valid readings "
                f"near '{location_str}'."
            )

        # ── Step 4: Aggregate to mean annual precipitation ────────────────────
        # Group monthly totals by year, sum to annual totals, then average.
        df_precip = precip_series.reset_index()
        df_precip["year"] = df_precip["time"].dt.year
        annual_totals = df_precip.groupby("year")[_PRECIP_COL].sum()

        years_used = len(annual_totals)
        if years_used == 0:
            return _fallback(f"Could not compute annual totals for '{location_str}'.")

        mean_annual_mm = float(annual_totals.mean())

        # ── Step 5: Compute index ─────────────────────────────────────────────
        precip_index = mean_annual_mm / PRECIP_INDEX_BASELINE_MM

        # ── Step 6: Retrieve best station name (best-effort) ─────────────────
        station_name: str | None = None
        try:
            # meteostat ≥ 1.6 exposes the matched stations via Monthly.stations()
            stations = monthly_data.stations()
            if stations is not None and not stations.empty:
                station_name = str(stations.iloc[0].get("name", "Unknown Station"))
        except Exception:
            station_name = "Unknown Station"

        return {
            "precip_index":   round(precip_index, 4),
            "mean_annual_mm": round(mean_annual_mm, 1),
            "station_name":   station_name or f"Near ({lat:.3f}, {lon:.3f})",
            "lat":            lat,
            "lon":            lon,
            "years_used":     years_used,
            "error":          None,
        }

    except Exception as exc:
        # Catch-all: network failures, API changes, unexpected meteostat errors.
        return _fallback(
            f"Unexpected error fetching precipitation data for '{location_str}': {exc}"
        )
