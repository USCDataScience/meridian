import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db as store
from . import concepts as conceptlib
from .index import rematch_concepts
from .paths import WEB_DIST

app = FastAPI(title="Meridian")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db():
    return store.connect()


def _filtered_ids(db, q=None, concept=None, place=None, year_min=None, year_max=None, unit=None):
    sql = "SELECT DISTINCT d.id FROM documents d"
    joins = []
    where = ["1=1"]
    args = []
    if q:
        joins.append("JOIN documents_fts f ON f.rowid = d.id")
        where.append("documents_fts MATCH ?")
        args.append(q)
    if concept:
        joins.append("JOIN concept_hits ch ON ch.document_id = d.id")
        where.append("ch.concept_id = ?")
        args.append(concept)
    if place:
        joins.append("JOIN places p ON p.document_id = d.id")
        where.append("LOWER(TRIM(p.name)) = LOWER(TRIM(?))")
        args.append(place)
    if year_min is not None or year_max is not None:
        joins.append("JOIN times t ON t.document_id = d.id")
        if year_min is not None:
            where.append("t.year >= ?")
            args.append(int(year_min))
        if year_max is not None:
            where.append("t.year <= ?")
            args.append(int(year_max))
    if unit:
        joins.append("JOIN quantities qn ON qn.document_id = d.id")
        where.append("qn.unit = ?")
        args.append(unit)
    sql = sql + " " + " ".join(joins) + " WHERE " + " AND ".join(where)
    try:
        return [r["id"] for r in db.execute(sql, args).fetchall()]
    except Exception:
        return []


def _in(ids):
    return ",".join("?" * len(ids))


def _agg(db, col, ids):
    if not ids:
        return {"max": None, "avg": None, "sum": None}
    row = db.execute(
        f"SELECT MAX({col}) mx, AVG({col}) av, SUM({col}) sm FROM documents WHERE id IN ({_in(ids)})",
        ids,
    ).fetchone()
    return {"max": row["mx"], "avg": row["av"], "sum": row["sm"]}


@app.get("/api/stats")
def stats(q: str | None = None, concept: str | None = None, place: str | None = None,
          year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    n = len(ids)
    empty = {"max": None, "avg": None, "sum": None}
    mime, langs, yields = [], [], []
    if ids:
        mime = [dict(r) for r in db.execute(
            f"SELECT COALESCE(mime,'unknown') AS mime, COUNT(*) AS count FROM documents WHERE id IN ({_in(ids)}) GROUP BY mime ORDER BY count DESC",
            ids,
        )]
        langs = [dict(r) for r in db.execute(
            f"SELECT COALESCE(language,'unknown') AS language, COUNT(*) AS count FROM documents WHERE id IN ({_in(ids)}) GROUP BY language ORDER BY count DESC",
            ids,
        )]
        for r in db.execute(
            f"SELECT file_size, text_size, meta_size, ttr FROM documents WHERE id IN ({_in(ids)})",
            ids,
        ):
            fs = r["file_size"] or 0
            yields.append({
                "text_yield": (r["text_size"] / fs) if fs else None,
                "meta_yield": (r["meta_size"] / fs) if fs else None,
                "ttr": r["ttr"],
            })
    text_yields = [y["text_yield"] for y in yields if y["text_yield"] is not None]
    meta_yields = [y["meta_yield"] for y in yields if y["meta_yield"] is not None]
    ttrs = [y["ttr"] for y in yields if y["ttr"] is not None]
    return {
        "documents": n,
        "places": 0 if not ids else db.execute(
            f"SELECT COUNT(DISTINCT name) c FROM places WHERE document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "years": 0 if not ids else db.execute(
            f"SELECT COUNT(DISTINCT year) c FROM times WHERE document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "concepts": 0 if not ids else db.execute(
            f"SELECT COUNT(DISTINCT concept_id) c FROM concept_hits WHERE document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "quantities": 0 if not ids else db.execute(
            f"SELECT COUNT(*) c FROM quantities WHERE document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "file_size": _agg(db, "file_size", ids) if ids else empty,
        "text_size": _agg(db, "text_size", ids) if ids else empty,
        "meta_size": _agg(db, "meta_size", ids) if ids else empty,
        "word_count": _agg(db, "word_count", ids) if ids else empty,
        "unique_terms": _agg(db, "unique_terms", ids) if ids else empty,
        "text_yield_avg": sum(text_yields) / len(text_yields) if text_yields else None,
        "meta_yield_avg": sum(meta_yields) / len(meta_yields) if meta_yields else None,
        "ttr_avg": sum(ttrs) / len(ttrs) if ttrs else None,
        "mime": mime,
        "languages": langs,
    }


@app.get("/api/documents")
def documents(q: str | None = None, concept: str | None = None, place: str | None = None,
              year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    rows = db.execute(
        f"""SELECT id, path, filename, mime, year, file_size, text_size, meta_size,
                   language, word_count, unique_terms, ttr
            FROM documents WHERE id IN ({_in(ids)}) ORDER BY filename""",
        ids,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        fs = d.get("file_size") or 0
        d["text_yield"] = (d["text_size"] / fs) if fs and d.get("text_size") is not None else None
        d["meta_yield"] = (d["meta_size"] / fs) if fs and d.get("meta_size") is not None else None
        out.append(d)
    return out


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    db = _db()
    row = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except json.JSONDecodeError:
        d["metadata"] = {}
    fs = d.get("file_size") or 0
    d["text_yield"] = (d["text_size"] / fs) if fs and d.get("text_size") is not None else None
    d["meta_yield"] = (d["meta_size"] / fs) if fs and d.get("meta_size") is not None else None
    d["places"] = [dict(r) for r in db.execute(
        "SELECT name, lat, lon, count FROM places WHERE document_id=? ORDER BY count DESC", (doc_id,))]
    d["times"] = [dict(r) for r in db.execute(
        "SELECT year, month, surface FROM times WHERE document_id=? ORDER BY year, month", (doc_id,))]
    d["years"] = sorted({t["year"] for t in d["times"]})
    d["concepts"] = [dict(r) for r in db.execute(
        "SELECT concept_id, label, hits FROM concept_hits WHERE document_id=?", (doc_id,))]
    d["quantities"] = [dict(r) for r in db.execute(
        "SELECT value, unit, surface FROM quantities WHERE document_id=? LIMIT 200", (doc_id,))]
    d["text"] = (d.get("text") or "")[:12000]
    return d


@app.get("/api/places")
def places(q: str | None = None, concept: str | None = None, place: str | None = None,
           year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    qmarks = ",".join("?" * len(ids))
    rows = db.execute(
        f"""SELECT name, lat, lon, SUM(count) AS count
            FROM places WHERE document_id IN ({qmarks})
            GROUP BY name ORDER BY count DESC""",
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/timeline")
def timeline(q: str | None = None, concept: str | None = None, place: str | None = None,
             year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return {"years": [], "heatmap": [], "decades": []}
    qmarks = _in(ids)
    years = [dict(r) for r in db.execute(
        f"""SELECT year, COUNT(*) AS mentions, COUNT(DISTINCT document_id) AS documents
            FROM times WHERE document_id IN ({qmarks})
            GROUP BY year ORDER BY year""",
        ids,
    )]
    heatmap = [dict(r) for r in db.execute(
        f"""SELECT year, month, COUNT(*) AS mentions, COUNT(DISTINCT document_id) AS documents
            FROM times WHERE document_id IN ({qmarks}) AND month IS NOT NULL
            GROUP BY year, month ORDER BY year, month""",
        ids,
    )]
    decades = [dict(r) for r in db.execute(
        f"""SELECT (year / 10) * 10 AS decade, COUNT(*) AS mentions, COUNT(DISTINCT document_id) AS documents
            FROM times WHERE document_id IN ({qmarks})
            GROUP BY decade ORDER BY decade""",
        ids,
    )]
    return {"years": years, "heatmap": heatmap, "decades": decades}


@app.get("/api/concepts")
def concepts(q: str | None = None, concept: str | None = None, place: str | None = None,
             year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    lib = conceptlib.load()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    counts = {}
    if ids:
        qmarks = ",".join("?" * len(ids))
        for r in db.execute(
            f"""SELECT concept_id, SUM(hits) AS hits
                FROM concept_hits WHERE document_id IN ({qmarks})
                GROUP BY concept_id""",
            ids,
        ):
            counts[r["concept_id"]] = r["hits"]
    return [{"id": c["id"], "label": c["label"], "aliases": c["aliases"], "hits": counts.get(c["id"], 0)} for c in lib]


class ConceptIn(BaseModel):
    id: str
    label: str
    aliases: list[str] = []


@app.post("/api/concepts")
def add_concept(body: ConceptIn):
    lib = conceptlib.load()
    if any(c["id"] == body.id for c in lib):
        raise HTTPException(400, "concept id exists")
    aliases = [body.label] + [a for a in body.aliases if a]
    lib.append({"id": body.id, "label": body.label, "aliases": aliases})
    conceptlib.save(lib)
    rematch_concepts()
    return {"ok": True}


def _qty_clause(ids, unit=None, mq=None, value_min=None, value_max=None):
    where = [f"qn.document_id IN ({_in(ids)})"]
    args = list(ids)
    if unit:
        where.append("qn.unit = ?")
        args.append(unit)
    if mq:
        where.append("(qn.unit LIKE ? OR qn.surface LIKE ?)")
        like = f"%{mq}%"
        args.extend([like, like])
    if value_min is not None:
        where.append("qn.value >= ?")
        args.append(float(value_min))
    if value_max is not None:
        where.append("qn.value <= ?")
        args.append(float(value_max))
    return " AND ".join(where), args


@app.get("/api/measurements")
def measurements(q: str | None = None, concept: str | None = None, place: str | None = None,
                 year_min: int | None = None, year_max: int | None = None, unit: str | None = None,
                 mq: str | None = None, value_min: float | None = None, value_max: float | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    clause, args = _qty_clause(ids, unit=unit, mq=mq, value_min=value_min, value_max=value_max)
    rows = db.execute(
        f"""SELECT qn.unit AS unit, COUNT(*) AS count, AVG(qn.value) AS avg,
                   MIN(qn.value) AS min, MAX(qn.value) AS max,
                   COUNT(DISTINCT qn.document_id) AS documents
            FROM quantities qn WHERE {clause} AND qn.unit IS NOT NULL AND qn.unit != ''
            GROUP BY qn.unit ORDER BY count DESC LIMIT 40""",
        args,
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/measurements/hits")
def measurement_hits(q: str | None = None, concept: str | None = None, place: str | None = None,
                     year_min: int | None = None, year_max: int | None = None, unit: str | None = None,
                     mq: str | None = None, value_min: float | None = None, value_max: float | None = None,
                     limit: int = 80):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    clause, args = _qty_clause(ids, unit=unit, mq=mq, value_min=value_min, value_max=value_max)
    rows = db.execute(
        f"""SELECT qn.value AS value, qn.unit AS unit, qn.surface AS surface,
                   d.id AS document_id, d.filename AS filename
            FROM quantities qn JOIN documents d ON d.id = qn.document_id
            WHERE {clause} ORDER BY qn.unit, qn.value LIMIT ?""",
        args + [min(limit, 200)],
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/measurements/histogram")
def measurement_histogram(unit: str, q: str | None = None, concept: str | None = None,
                          place: str | None = None, year_min: int | None = None,
                          year_max: int | None = None, bins: int = 12):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    rows = db.execute(
        f"""SELECT value FROM quantities WHERE document_id IN ({_in(ids)})
            AND unit = ? AND value IS NOT NULL ORDER BY value""",
        list(ids) + [unit],
    ).fetchall()
    values = [r["value"] for r in rows]
    if not values:
        return []
    lo, hi = min(values), max(values)
    n = max(1, min(bins, 24))
    if lo == hi:
        return [{"lo": lo, "hi": hi, "count": len(values)}]
    width = (hi - lo) / n
    counts = [0] * n
    for v in values:
        i = min(n - 1, int((v - lo) / width))
        counts[i] += 1
    return [{"lo": lo + i * width, "hi": lo + (i + 1) * width, "count": counts[i]} for i in range(n)]


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="ui")


def run(host="127.0.0.1", port=8090):
    import uvicorn
    if not WEB_DIST.exists():
        print("UI not built (web/dist missing). API only.")
        print("  cd web && npm install && npm run build")
    uvicorn.run(app, host=host, port=port, log_level="info")
