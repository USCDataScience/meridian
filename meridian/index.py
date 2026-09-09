from collections import Counter
from datetime import datetime
from pathlib import Path

from . import db as store
from . import extract
from . import geo
from . import concepts as conceptlib

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "data", "web",
    "facets-view", "Docker", "insight-generator", "insight-visualizer",
}
DOC_EXT = {
    ".pdf", ".txt", ".html", ".htm", ".xml", ".doc", ".docx",
    ".ppt", ".pptx", ".xls", ".xlsx", ".md", ".csv", ".tsv",
    ".rtf", ".odt", ".json",
}


def walk(paths):
    files = []
    for raw in paths:
        p = Path(raw).resolve()
        if p.is_file():
            files.append(p)
            continue
        if not p.is_dir():
            print(f"skip (not found): {p}")
            continue
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if any(part in SKIP_DIRS or part.startswith(".") for part in f.parts):
                continue
            if f.name.startswith("."):
                continue
            if f.suffix.lower() not in DOC_EXT:
                continue
            files.append(f)
    return files


def index_paths(paths, resolve_geo=True):
    files = walk(paths)
    if not files:
        print("Nothing to index.")
        return 0
    conn = store.connect()
    lib = conceptlib.load()
    if resolve_geo:
        geo.ensure()
    n = 0
    total = len(files)
    for i, f in enumerate(files, 1):
        rel = str(f)
        print(f"index [{i}/{total}] {rel}")
        try:
            text, mime, meta, xhtml = extract.tika_parse(f)
        except Exception as e:
            print(f"  tika failed: {e}")
            continue
        ner = extract.analyze(text)
        places = ner["places"]
        times = extract.times_from_text(text, meta, ner["dates"])
        years = [t["year"] for t in times]
        year = Counter(years).most_common(1)[0][0] if years else None
        stats = extract.text_stats(text, f, meta, xhtml)
        existing = store.document_id_for_path(conn, rel)
        if existing:
            store.clear_document_annotations(conn, existing)
            conn.execute("DELETE FROM documents WHERE id=?", (existing,))
        doc_id = store.insert_document(conn, rel, f.name, mime, text, year, stats)
        placed = _store_places(conn, doc_id, places, resolve_geo)
        n_ent = _store_entities(conn, doc_id, ner["people"], ner["orgs"])
        for t in times:
            conn.execute(
                "INSERT INTO times(document_id, year, month, surface) VALUES (?,?,?,?)",
                (doc_id, t["year"], t["month"], t["surface"]),
            )
        for q in extract.quantities(text):
            conn.execute(
                "INSERT INTO quantities(document_id, value, unit, surface) VALUES (?,?,?,?)",
                (doc_id, q["value"], q["unit"], q["surface"]),
            )
        for hit in conceptlib.match(text, lib):
            conn.execute(
                "INSERT INTO concept_hits(document_id, concept_id, label, hits) VALUES (?,?,?,?)",
                (doc_id, hit["id"], hit["label"], hit["hits"]),
            )
        conn.commit()
        n += 1
        print(
            f"  {mime or 'unknown'}  year={year}  places={placed}/{len(places)}  "
            f"who={n_ent}  times={len(times)}  yield={stats.get('text_yield')}"
        )
    print(f"indexed {n} file(s) at {datetime.now():%H:%M:%S}")
    return n


def _store_places(conn, doc_id, places, resolve_geo):
    if resolve_geo:
        resolved = geo.resolve(places)
        for item in resolved:
            conn.execute(
                "INSERT INTO places(document_id, name, lat, lon, count) VALUES (?,?,?,?,?)",
                (doc_id, item["name"], item["lat"], item["lon"], item["count"]),
            )
        return len(resolved)
    for name, count in places.items():
        conn.execute(
            "INSERT INTO places(document_id, name, lat, lon, count) VALUES (?,?,?,?,?)",
            (doc_id, name, None, None, count),
        )
    return len(places)


def _store_entities(conn, doc_id, people, orgs):
    n = 0
    for name, count in (people or {}).items():
        conn.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (?,?,?,?)",
            (doc_id, name, "PERSON", count),
        )
        n += 1
    for name, count in (orgs or {}).items():
        conn.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (?,?,?,?)",
            (doc_id, name, "ORG", count),
        )
        n += 1
    return n


def regeocode(resolve_geo=True):
    """Re-NER places/people/orgs from stored text; resolve places against the gazetteer."""
    conn = store.connect()
    rows = conn.execute("SELECT id, filename, text FROM documents").fetchall()
    if not rows:
        print("Nothing to geocode.")
        return 0
    if resolve_geo:
        geo.ensure()
    total = len(rows)
    n = 0
    hits = 0
    mentioned = 0
    who = 0
    for i, row in enumerate(rows, 1):
        ner = extract.analyze(row["text"] or "")
        places = ner["places"]
        mentioned += len(places)
        conn.execute("DELETE FROM places WHERE document_id=?", (row["id"],))
        conn.execute("DELETE FROM entities WHERE document_id=?", (row["id"],))
        placed = _store_places(conn, row["id"], places, resolve_geo)
        who += _store_entities(conn, row["id"], ner["people"], ner["orgs"])
        hits += placed
        conn.commit()
        n += 1
        print(
            f"geocode [{i}/{total}] {row['filename']}  "
            f"{placed}/{len(places)} places  people={len(ner['people'])} orgs={len(ner['orgs'])}"
        )
    print(f"geocoded {n} document(s), {hits}/{mentioned} places resolved, {who} person/org names")
    return n


def rematch_concepts(conn=None):
    conn = conn or store.connect()
    lib = conceptlib.load()
    conn.execute("DELETE FROM concept_hits")
    rows = conn.execute("SELECT id, text FROM documents").fetchall()
    for row in rows:
        for hit in conceptlib.match(row["text"], lib):
            conn.execute(
                "INSERT INTO concept_hits(document_id, concept_id, label, hits) VALUES (?,?,?,?)",
                (row["id"], hit["id"], hit["label"], hit["hits"]),
            )
    conn.commit()
