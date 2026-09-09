"""AND across axes, OR within an axis."""

from dataclasses import dataclass, field


def _list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if x is not None and str(x).strip() != ""]
    s = str(v).strip()
    return [s] if s else []


def parse_year(s):
    raw = (s or "").strip()
    if not raw:
        return None
    if "," in raw and "-" not in raw[1:]:
        return None
    if raw.count("-") == 1:
        a, b = raw.split("-", 1)
        lo = int(a) if a.strip() else None
        hi = int(b) if b.strip() else None
        return (lo, hi)
    y = int(raw)
    return (y, y)


def parse_bbox(s):
    parts = [p.strip() for p in (s or "").split(",")]
    if len(parts) != 4:
        return None
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        return None
    if south > north:
        south, north = north, south
    if west == east or south == north:
        return None
    return {"west": west, "south": south, "east": east, "north": north}


@dataclass
class Filters:
    q: str | None = None
    concepts: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    persons: list[str] = field(default_factory=list)
    orgs: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    years: list[tuple] = field(default_factory=list)
    bboxes: list[dict] = field(default_factory=list)

    @classmethod
    def from_params(cls, q=None, concept=None, place=None, person=None, org=None,
                    unit=None, year=None, year_min=None, year_max=None, bbox=None):
        years = [y for y in (parse_year(s) for s in _list(year)) if y]
        if not years and (year_min is not None or year_max is not None):
            years = [(year_min, year_max)]
        return cls(
            q=(q.strip() if q and q.strip() else None),
            concepts=_list(concept),
            places=_list(place),
            persons=_list(person),
            orgs=_list(org),
            units=_list(unit),
            years=years,
            bboxes=[b for b in (parse_bbox(s) for s in _list(bbox)) if b],
        )


def _expand_entities(db, label, names):
    from .names import aliases_for
    rows = db.execute(
        "SELECT DISTINCT name FROM entities WHERE label=?", (label,)
    ).fetchall()
    catalog = [r["name"] if not isinstance(r, tuple) else r[0] for r in rows]
    return aliases_for(catalog, names, kind=label) or list(names)


def _in_list(column, values, args, lower=False):
    qs = ",".join("?" * len(values))
    if lower:
        args.extend(v.lower() for v in values)
        return f"LOWER(TRIM({column})) IN ({qs})"
    args.extend(values)
    return f"{column} IN ({qs})"


def filtered_ids(db, f: Filters):
    sql = "SELECT DISTINCT d.id FROM documents d"
    where = ["1=1"]
    args = []
    if f.q:
        sql += " JOIN documents_fts fts ON fts.rowid = d.id"
        where.append("documents_fts MATCH ?")
        args.append(f.q)
    if f.concepts:
        clause = _in_list("concept_id", f.concepts, args)
        where.append(f"d.id IN (SELECT document_id FROM concept_hits WHERE {clause})")
    if f.places:
        clause = _in_list("name", f.places, args, lower=True)
        where.append(f"d.id IN (SELECT document_id FROM places WHERE {clause})")
    if f.persons:
        people = _expand_entities(db, "PERSON", f.persons)
        clause = _in_list("name", people, args, lower=True)
        where.append(
            f"d.id IN (SELECT document_id FROM entities WHERE label='PERSON' AND {clause})"
        )
    if f.orgs:
        orgs = _expand_entities(db, "ORG", f.orgs)
        clause = _in_list("name", orgs, args, lower=True)
        where.append(
            f"d.id IN (SELECT document_id FROM entities WHERE label='ORG' AND {clause})"
        )
    if f.units:
        clause = _in_list("unit", f.units, args)
        where.append(f"d.id IN (SELECT document_id FROM quantities WHERE {clause})")
    if f.years:
        parts = []
        for lo, hi in f.years:
            if lo is not None and hi is not None:
                parts.append("(year >= ? AND year <= ?)")
                args.extend([int(lo), int(hi)])
            elif lo is not None:
                parts.append("year >= ?")
                args.append(int(lo))
            elif hi is not None:
                parts.append("year <= ?")
                args.append(int(hi))
        if parts:
            where.append(
                "d.id IN (SELECT document_id FROM times WHERE " + " OR ".join(parts) + ")"
            )
    if f.bboxes:
        parts = []
        for b in f.bboxes:
            west, east = b["west"], b["east"]
            south, north = b["south"], b["north"]
            if west <= east:
                parts.append("(lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)")
                args.extend([south, north, west, east])
            else:
                parts.append(
                    "(lat BETWEEN ? AND ? AND (lon >= ? OR lon <= ?))"
                )
                args.extend([south, north, west, east])
        where.append(
            "d.id IN (SELECT document_id FROM places WHERE lat IS NOT NULL AND ("
            + " OR ".join(parts)
            + "))"
        )
    sql += " WHERE " + " AND ".join(where)
    try:
        return [r["id"] for r in db.execute(sql, args).fetchall()]
    except Exception:
        return []
