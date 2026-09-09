"""Resolve GPE/LOC mentions against the local GeoNames gazetteer."""

import math
from collections import Counter

from . import geonames

KIND_BONUS = {
    "country": 5.0,
    "admin1": 3.0,
    "city": 0.0,
    "region": 7.0,
}
FEATURE_BONUS = {
    "PPLC": 2.5,
    "PPLA": 1.5,
    "PPLA2": 0.5,
    "PCLI": 1.0,
    "ADM1": 0.5,
}
COUNTRY_CONTEXT = 8.0
ADMIN1_CONTEXT = 4.0

_gaz = None
_index = None


def ensure():
    geonames.ensure()
    _load()


def _load(db=None):
    global _gaz, _index
    if db is not None:
        return _build_index(db)
    if _index is not None:
        return _index
    geonames.ensure()
    _gaz = geonames.connect()
    _index = _build_index(_gaz)
    return _index


def _build_index(db):
    out = {}
    for row in db.execute(
        "SELECT name_norm, display, lat, lon, country, admin1, kind, feature, population FROM names"
    ):
        out.setdefault(row["name_norm"], []).append(row)
    return out


def _candidates(name, index):
    seen = set()
    hits = []
    for key in geonames.query_keys(name):
        for row in index.get(key) or ():
            ident = (row["lat"], row["lon"], row["kind"], row["country"], row["admin1"])
            if ident in seen:
                continue
            seen.add(ident)
            hits.append(row)
    return hits


def _country_context(mentions, index):
    codes = set()
    for name in mentions:
        rows = _candidates(name, index)
        countries = {r["country"] for r in rows if r["kind"] == "country" and r["country"]}
        if len(countries) != 1:
            continue
        cc = next(iter(countries))
        # "Georgia" is a country and a US state — not country context by itself.
        if any(r["kind"] == "admin1" and r["country"] != cc for r in rows):
            continue
        codes.add(cc)
    return codes


def _admin1_contrib(mentions, index, country_codes):
    """Per-mention admin1 vote: named states and first-pass cities."""
    empty = Counter()
    contrib = {}
    for name, count in mentions.items():
        rows = _candidates(name, index)
        if not rows:
            continue
        best = pick(rows, country_codes, empty)
        if not best or not best["admin1"]:
            continue
        kinds = {r["kind"] for r in rows}
        if best["kind"] == "admin1" and "country" not in kinds:
            contrib[name] = ((best["country"], best["admin1"]), count)
        elif best["kind"] == "city":
            contrib[name] = ((best["country"], best["admin1"]), count)
    return contrib


def _weights_without(contrib, skip_name):
    weights = Counter()
    for name, (key, count) in contrib.items():
        if name == skip_name:
            continue
        weights[key] += count
    return weights


def score(row, country_codes, admin1_weights):
    pop = row["population"] or 0
    s = math.log10(pop + 1)
    s += KIND_BONUS.get(row["kind"] or "", 0.0)
    s += FEATURE_BONUS.get(row["feature"] or "", 0.0)
    if row["country"] and row["country"] in country_codes:
        s += COUNTRY_CONTEXT
    if row["admin1"]:
        s += ADMIN1_CONTEXT * admin1_weights.get((row["country"], row["admin1"]), 0)
    return s


def pick(rows, country_codes, admin1_weights):
    if not rows:
        return None
    return max(rows, key=lambda r: score(r, country_codes, admin1_weights))


def resolve(mentions, gaz=None):
    """Map {name: count} to gazetteer hits. Names not in the gazetteer are dropped."""
    if not mentions:
        return []
    index = _load(gaz) if gaz is not None else _load()
    country_codes = _country_context(mentions, index)
    contrib = _admin1_contrib(mentions, index, country_codes)
    out = []
    for name, count in mentions.items():
        rows = _candidates(name, index)
        if not rows:
            continue
        best = pick(rows, country_codes, _weights_without(contrib, name))
        if best is None:
            continue
        out.append({
            "name": name,
            "lat": best["lat"],
            "lon": best["lon"],
            "count": count,
            "display": best["display"],
            "kind": best["kind"],
            "country": best["country"],
        })
    return out


def lookup(db, name):
    """Single-name resolve without document context. db is unused (API compat)."""
    hits = resolve({name: 1})
    if not hits:
        return None, None, None
    h = hits[0]
    return h["lat"], h["lon"], h["display"]
