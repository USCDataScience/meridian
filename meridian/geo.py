"""Resolve place names to lat/lon. Nominatim, cached in sqlite, skipped on failure."""

import time

_geocoder = None


def _coder():
    global _geocoder
    if _geocoder is None:
        from geopy.geocoders import Nominatim
        _geocoder = Nominatim(user_agent="meridian-usc-irds", timeout=8)
    return _geocoder


def lookup(db, name):
    key = name.strip()
    if not key:
        return None, None, None
    cached = db.execute(
        "SELECT lat, lon, display FROM place_cache WHERE name=?", (key.lower(),)
    ).fetchone()
    if cached:
        return cached["lat"], cached["lon"], cached["display"]
    lat = lon = display = None
    try:
        loc = _coder().geocode(key)
        time.sleep(1.05)
        if loc:
            lat, lon = loc.latitude, loc.longitude
            display = loc.address
        db.execute(
            "INSERT OR REPLACE INTO place_cache(name, lat, lon, display) VALUES (?,?,?,?)",
            (key.lower(), lat, lon, display),
        )
        db.commit()
    except Exception:
        # Network / Nominatim errors are not cached, so a later index can retry.
        pass
    return lat, lon, display
