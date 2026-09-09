"""Local GeoNames gazetteer: cities15000 + countries + admin1. No Docker."""

import sqlite3
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from .paths import DATA_DIR, GAZETTEER_PATH, ensure_data

DUMP = "https://download.geonames.org/export/dump"
GAZ_PATH = GAZETTEER_PATH
RAW_DIR = DATA_DIR / "geonames"
SCHEMA_VERSION = 1
UA = "meridian-usc-irds"

# Continents, oceans, and a few regions cities15000 does not cover.
REGIONS = (
    ("Africa", 1.0, 17.0),
    ("Antarctica", -82.0, 0.0),
    ("Asia", 45.0, 90.0),
    ("Europe", 54.0, 15.0),
    ("North America", 46.0, -100.0),
    ("South America", -15.0, -60.0),
    ("Oceania", -18.0, 140.0),
    ("Central America", 12.0, -85.0),
    ("Arctic", 90.0, 0.0),
    ("Antarctic", -90.0, 0.0),
    ("Siberia", 60.0, 100.0),
    ("Arctic Ocean", 80.0, 0.0),
    ("Atlantic Ocean", 0.0, -30.0),
    ("Pacific Ocean", 0.0, -160.0),
    ("Indian Ocean", -20.0, 80.0),
    ("Southern Ocean", -60.0, 0.0),
    ("Atlantic", 0.0, -30.0),
    ("Pacific", 0.0, -160.0),
    ("Mediterranean", 35.0, 18.0),
    ("Mediterranean Sea", 35.0, 18.0),
    ("Caribbean", 15.0, -75.0),
    ("Middle East", 29.0, 42.0),
)

# Extra English names for countries; ISO2 itself is not indexed (too noisy).
COUNTRY_ALIASES = {
    "US": ("USA", "U.S.", "U.S.A.", "United States of America", "United States"),
    "GB": ("UK", "U.K.", "Great Britain", "Britain"),
    "KR": ("South Korea", "Republic of Korea"),
    "KP": ("North Korea", "DPRK"),
    "RU": ("Russia",),
    "VN": ("Vietnam",),
    "CZ": ("Czech Republic", "Czechia"),
    "NL": ("Holland", "The Netherlands"),
    "AE": ("UAE", "U.A.E."),
    "MM": ("Burma",),
    "CD": ("DRC",),
    "CI": ("Ivory Coast",),
    "IR": ("Iran",),
    "SY": ("Syria",),
    "LA": ("Laos",),
    "MD": ("Moldova",),
    "MK": ("North Macedonia", "Macedonia"),
    "TZ": ("Tanzania",),
    "BO": ("Bolivia",),
    "VE": ("Venezuela",),
    "VA": ("Vatican", "Vatican City"),
    "PS": ("Palestine",),
    "SZ": ("Swaziland", "Eswatini"),
    "TL": ("East Timor",),
    "CV": ("Cape Verde",),
    "BN": ("Brunei",),
    "FM": ("Micronesia",),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS names (
  name_norm TEXT NOT NULL,
  display TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  country TEXT,
  admin1 TEXT,
  kind TEXT NOT NULL,
  feature TEXT,
  population INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_names_norm ON names(name_norm);
"""

INSERT = (
    "INSERT INTO names(name_norm, display, lat, lon, country, admin1, kind, feature, population) "
    "VALUES (?,?,?,?,?,?,?,?,?)"
)


def norm(name):
    s = (name or "").strip().lower()
    s = s.replace(".", "").replace("'", "")
    s = " ".join(s.split())
    if s.startswith("the "):
        s = s[4:]
    return s


def query_keys(name):
    n = norm(name)
    keys = {n}
    if n.startswith("st "):
        keys.add("saint " + n[3:])
    elif n.startswith("saint "):
        keys.add("st " + n[6:])
    return {k for k in keys if k}


def _keep_name(n):
    if not n or len(n) < 2:
        return False
    if n.isdigit():
        return False
    if len(n) == 2 and n not in {"uk"}:
        return False
    return True


def _download(filename):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / filename
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = f"{DUMP}/{filename}"
    print(f"download {url}")
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    return dest


def _cities_path():
    txt = RAW_DIR / "cities15000.txt"
    if txt.exists() and txt.stat().st_size > 0:
        return txt
    zpath = _download("cities15000.zip")
    with zipfile.ZipFile(zpath) as zf:
        zf.extract("cities15000.txt", RAW_DIR)
    return txt


def _fetch_dumps():
    cities = _cities_path()
    countries = _download("countryInfo.txt")
    admin1 = _download("admin1CodesASCII.txt")
    return cities, countries, admin1


def _city_rows(path):
    cities = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 15:
                continue
            try:
                lat = float(cols[4])
                lon = float(cols[5])
                pop = int(cols[14] or 0)
            except ValueError:
                continue
            cities.append({
                "name": cols[1],
                "ascii": cols[2],
                "lat": lat,
                "lon": lon,
                "feature": cols[7],
                "country": cols[8],
                "admin1": cols[10],
                "population": pop,
            })
    return cities


def _country_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 9 or len(cols[0]) != 2:
                continue
            try:
                pop = int(cols[7] or 0)
            except ValueError:
                pop = 0
            rows.append({
                "iso": cols[0],
                "name": cols[4],
                "capital": cols[5],
                "population": pop,
                "continent": cols[8],
            })
    return rows


def _admin1_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3 or "." not in cols[0]:
                continue
            iso, code = cols[0].split(".", 1)
            rows.append({
                "country": iso,
                "admin1": code,
                "name": cols[1],
                "ascii": cols[2],
            })
    return rows


def _largest(rows):
    return max(rows, key=lambda r: r["population"]) if rows else None


def _country_point(iso, capital, by_cc, by_cc_name):
    cities = by_cc.get(iso) or []
    pplc = [c for c in cities if c["feature"] == "PPLC"]
    if pplc:
        return _largest(pplc)
    cap = by_cc_name.get((iso, norm(capital))) or []
    if cap:
        return _largest(cap)
    return _largest(cities)


def add_name(db, name, lat, lon, country, admin1, kind, feature, population, display=None):
    n = norm(name)
    if not _keep_name(n):
        return
    db.execute(
        INSERT,
        (n, display or name, lat, lon, country, admin1, kind, feature, int(population or 0)),
    )


def build(path=None, raw=None):
    """Build geonames.sqlite from GeoNames dumps. Downloads once if needed."""
    ensure_data()
    dest = Path(path) if path else GAZ_PATH
    if raw:
        cities_p, countries_p, admin1_p = raw
    else:
        cities_p, countries_p, admin1_p = _fetch_dumps()
    print(f"build gazetteer {dest}")
    cities = _city_rows(cities_p)
    countries = _country_rows(countries_p)
    admin1 = _admin1_rows(admin1_p)

    by_cc = {}
    by_cc_admin = {}
    by_cc_name = {}
    for c in cities:
        by_cc.setdefault(c["country"], []).append(c)
        by_cc_admin.setdefault((c["country"], c["admin1"]), []).append(c)
        by_cc_name.setdefault((c["country"], norm(c["name"])), []).append(c)
        if c["ascii"] and norm(c["ascii"]) != norm(c["name"]):
            by_cc_name.setdefault((c["country"], norm(c["ascii"])), []).append(c)

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    db = sqlite3.connect(dest)
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = OFF")
    db.executescript(SCHEMA)

    batch = []

    def flush():
        if batch:
            db.executemany(INSERT, batch)
            batch.clear()

    def queue(name, lat, lon, country, admin1, kind, feature, population, display=None):
        n = norm(name)
        if not _keep_name(n):
            return
        batch.append(
            (n, display or name, lat, lon, country, admin1, kind, feature, int(population or 0))
        )
        if len(batch) >= 5000:
            flush()

    for c in cities:
        queue(c["name"], c["lat"], c["lon"], c["country"], c["admin1"], "city",
              c["feature"], c["population"])
        if c["ascii"] and norm(c["ascii"]) != norm(c["name"]):
            queue(c["ascii"], c["lat"], c["lon"], c["country"], c["admin1"], "city",
                  c["feature"], c["population"], display=c["name"])

    country_pt = {}
    for co in countries:
        pt = _country_point(co["iso"], co["capital"], by_cc, by_cc_name)
        if not pt:
            continue
        country_pt[co["iso"]] = pt
        queue(co["name"], pt["lat"], pt["lon"], co["iso"], None, "country", "PCLI",
              co["population"])
        for alias in COUNTRY_ALIASES.get(co["iso"], ()):
            if norm(alias) != norm(co["name"]):
                queue(alias, pt["lat"], pt["lon"], co["iso"], None, "country", "PCLI",
                      co["population"], display=co["name"])

    for ad in admin1:
        cities_here = by_cc_admin.get((ad["country"], ad["admin1"])) or []
        pt = _largest(cities_here) or country_pt.get(ad["country"])
        if not pt:
            continue
        pop = pt["population"] if cities_here else 0
        queue(ad["name"], pt["lat"], pt["lon"], ad["country"], ad["admin1"], "admin1",
              "ADM1", pop)
        if ad["ascii"] and norm(ad["ascii"]) != norm(ad["name"]):
            queue(ad["ascii"], pt["lat"], pt["lon"], ad["country"], ad["admin1"], "admin1",
                  "ADM1", pop, display=ad["name"])

    for name, lat, lon in REGIONS:
        queue(name, lat, lon, None, None, "region", None, 0)

    flush()
    db.execute("INSERT INTO meta(key, value) VALUES ('version', ?)", (str(SCHEMA_VERSION),))
    db.execute("INSERT INTO meta(key, value) VALUES ('cities', ?)", (str(len(cities)),))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM names").fetchone()[0]
    db.close()
    print(f"gazetteer {n} names from {len(cities)} cities")
    return dest


def ready(path=None):
    dest = Path(path) if path else GAZ_PATH
    if not dest.exists() or dest.stat().st_size == 0:
        return False
    db = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        row = db.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        return bool(row) and row[0] == str(SCHEMA_VERSION)
    except sqlite3.Error:
        return False
    finally:
        db.close()


def connect(path=None):
    dest = Path(path) if path else GAZ_PATH
    db = sqlite3.connect(dest)
    db.row_factory = sqlite3.Row
    return db


def ensure(path=None):
    dest = Path(path) if path else GAZ_PATH
    if not ready(dest):
        build(dest)
    return dest


def memory_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db
