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
    n = 0
    for f in files:
        rel = str(f)
        print(f"index {rel}")
        try:
            text, mime, meta = extract.tika_parse(f)
        except Exception as e:
            print(f"  tika failed: {e}")
            continue
        years = extract.years_from_text(text, meta)
        year = Counter(years).most_common(1)[0][0] if years else None
        existing = store.document_id_for_path(conn, rel)
        if existing:
            store.clear_document_annotations(conn, existing)
            conn.execute("DELETE FROM documents WHERE id=?", (existing,))
        doc_id = store.insert_document(conn, rel, f.name, mime, text, year)
        places, _dates = extract.analyze(text)
        for name, count in places.items():
            lat = lon = None
            if resolve_geo:
                lat, lon, _ = geo.lookup(conn, name)
            conn.execute(
                "INSERT INTO places(document_id, name, lat, lon, count) VALUES (?,?,?,?,?)",
                (doc_id, name, lat, lon, count),
            )
        for y in sorted(set(years)):
            conn.execute(
                "INSERT INTO times(document_id, year, surface) VALUES (?,?,?)",
                (doc_id, y, str(y)),
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
        print(f"  {mime or 'unknown'}  year={year}  places={len(places)}  years={len(set(years))}")
    print(f"indexed {n} file(s) at {datetime.now():%H:%M:%S}")
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
