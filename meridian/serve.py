import csv
import io
import json
import zipfile
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db as store
from . import concepts as conceptlib
from .filters import Filters, filtered_ids
from .index import rematch_concepts
from .names import collapse_orgs, collapse_people, idf_score
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


def query_filters(
    q: str | None = None,
    concept: list[str] | None = Query(None),
    place: list[str] | None = Query(None),
    person: list[str] | None = Query(None),
    org: list[str] | None = Query(None),
    unit: list[str] | None = Query(None),
    year: list[str] | None = Query(None),
    year_min: int | None = None,
    year_max: int | None = None,
    bbox: list[str] | None = Query(None),
) -> Filters:
    return Filters.from_params(
        q=q, concept=concept, place=place, person=person, org=org,
        unit=unit, year=year, year_min=year_min, year_max=year_max, bbox=bbox,
    )


FDep = Annotated[Filters, Depends(query_filters)]


def _filtered_ids(db, f: Filters):
    return filtered_ids(db, f)


def _in(ids):
    return ",".join("?" * len(ids))


def _score_rows(rows, n_docs, hits_key="hits", df_key="documents"):
    out = []
    n = n_docs or 0
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else dict(r)
        hits = d.get(hits_key) or 0
        df = d.get(df_key) or 0
        d["idf"] = round(idf_score(hits or 1, df, n), 4) if df else 0
        d["score"] = round(idf_score(hits, df, n), 4)
        out.append(d)
    return out


def _agg(db, col, ids):
    if not ids:
        return {"max": None, "avg": None, "sum": None}
    row = db.execute(
        f"SELECT MAX({col}) mx, AVG({col}) av, SUM({col}) sm FROM documents WHERE id IN ({_in(ids)})",
        ids,
    ).fetchone()
    return {"max": row["mx"], "avg": row["av"], "sum": row["sm"]}


@app.get("/api/stats")
def stats(f: FDep):
    db = _db()
    ids = _filtered_ids(db, f)
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
            f"""SELECT file_size, text_size, meta_size, ttr, tag_count,
                       word_count, unique_terms
                FROM documents WHERE id IN ({_in(ids)})""",
            ids,
        ):
            fs = r["file_size"] or 0
            wc = r["word_count"] or 0
            yields.append({
                "text_yield": (r["text_size"] / fs) if fs else None,
                "meta_yield": (r["meta_size"] / fs) if fs else None,
                "ttr": r["ttr"],
                "type_token": (r["unique_terms"] / wc) if wc else None,
            })
    text_yields = [y["text_yield"] for y in yields if y["text_yield"] is not None]
    meta_yields = [y["meta_yield"] for y in yields if y["meta_yield"] is not None]
    ttrs = [y["ttr"] for y in yields if y["ttr"] is not None]
    type_tokens = [y["type_token"] for y in yields if y["type_token"] is not None]
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
        "people": 0 if not ids else db.execute(
            f"SELECT COUNT(DISTINCT name) c FROM entities WHERE label='PERSON' AND document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "orgs": 0 if not ids else db.execute(
            f"SELECT COUNT(DISTINCT name) c FROM entities WHERE label='ORG' AND document_id IN ({_in(ids)})", ids
        ).fetchone()["c"],
        "file_size": _agg(db, "file_size", ids) if ids else empty,
        "text_size": _agg(db, "text_size", ids) if ids else empty,
        "meta_size": _agg(db, "meta_size", ids) if ids else empty,
        "word_count": _agg(db, "word_count", ids) if ids else empty,
        "unique_terms": _agg(db, "unique_terms", ids) if ids else empty,
        "text_yield_avg": sum(text_yields) / len(text_yields) if text_yields else None,
        "meta_yield_avg": sum(meta_yields) / len(meta_yields) if meta_yields else None,
        "ttr_avg": sum(ttrs) / len(ttrs) if ttrs else None,
        "type_token_avg": sum(type_tokens) / len(type_tokens) if type_tokens else None,
        "mime": mime,
        "languages": langs,
    }


@app.get("/api/documents")
def documents(f: FDep):
    db = _db()
    ids = _filtered_ids(db, f)
    if not ids:
        return []
    rows = db.execute(
        f"""SELECT id, path, filename, mime, year, file_size, text_size, meta_size,
                   language, word_count, unique_terms, ttr, tag_count
            FROM documents WHERE id IN ({_in(ids)}) ORDER BY filename""",
        ids,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        fs = d.get("file_size") or 0
        d["text_yield"] = (d["text_size"] / fs) if fs and d.get("text_size") is not None else None
        d["meta_yield"] = (d["meta_size"] / fs) if fs and d.get("meta_size") is not None else None
        wc = d.get("word_count") or 0
        d["type_token"] = (d["unique_terms"] / wc) if wc else None
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
    wc = d.get("word_count") or 0
    d["type_token"] = (d["unique_terms"] / wc) if wc else None
    d["places"] = [dict(r) for r in db.execute(
        "SELECT name, lat, lon, count FROM places WHERE document_id=? ORDER BY count DESC", (doc_id,))]
    d["times"] = [dict(r) for r in db.execute(
        "SELECT year, month, surface FROM times WHERE document_id=? ORDER BY year, month", (doc_id,))]
    d["years"] = sorted({t["year"] for t in d["times"]})
    d["concepts"] = [dict(r) for r in db.execute(
        "SELECT concept_id, label, hits FROM concept_hits WHERE document_id=?", (doc_id,))]
    d["quantities"] = [dict(r) for r in db.execute(
        "SELECT value, unit, surface FROM quantities WHERE document_id=? LIMIT 200", (doc_id,))]
    d["people"] = [dict(r) for r in db.execute(
        "SELECT name, count FROM entities WHERE document_id=? AND label='PERSON' ORDER BY count DESC",
        (doc_id,))]
    d["orgs"] = [dict(r) for r in db.execute(
        "SELECT name, count FROM entities WHERE document_id=? AND label='ORG' ORDER BY count DESC",
        (doc_id,))]
    d["text"] = (d.get("text") or "")[:12000]
    return d


@app.get("/api/places")
def places(f: FDep):
    db = _db()
    ids = _filtered_ids(db, f)
    if not ids:
        return []
    qmarks = ",".join("?" * len(ids))
    rows = db.execute(
        f"""SELECT name, lat, lon, SUM(count) AS count,
                   COUNT(DISTINCT document_id) AS documents
            FROM places WHERE document_id IN ({qmarks})
            GROUP BY name ORDER BY count DESC""",
        ids,
    ).fetchall()
    return _score_rows([dict(r) for r in rows], len(ids), hits_key="count")


@app.get("/api/timeline")
def timeline(f: FDep):
    db = _db()
    ids = _filtered_ids(db, f)
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
def concepts(f: FDep):
    db = _db()
    lib = conceptlib.load()
    ids = _filtered_ids(db, f)
    counts = {}
    if ids:
        qmarks = ",".join("?" * len(ids))
        for r in db.execute(
            f"""SELECT concept_id, SUM(hits) AS hits, COUNT(DISTINCT document_id) AS documents
                FROM concept_hits WHERE document_id IN ({qmarks})
                GROUP BY concept_id""",
            ids,
        ):
            counts[r["concept_id"]] = {"hits": r["hits"], "documents": r["documents"]}
    n = len(ids)
    out = []
    for c in lib:
        hit = counts.get(c["id"]) or {"hits": 0, "documents": 0}
        row = {"id": c["id"], "label": c["label"], "aliases": c["aliases"], **hit}
        scored = _score_rows([row], n)[0]
        out.append(scored)
    return out


class ConceptIn(BaseModel):
    id: str
    label: str
    aliases: list[str] = []


@app.get("/api/concepts/cooccur")
def concept_cooccur(f: FDep):
    """Other concepts in the same documents, plus pair counts for a graph."""
    db = _db()
    lib = conceptlib.load()
    labels = {c["id"]: c["label"] for c in lib}
    ids = _filtered_ids(db, f)
    if not ids:
        return {"nodes": [], "links": [], "other": []}
    qmarks = _in(ids)
    selected = set(f.concepts)
    nodes = []
    for r in db.execute(
        f"""SELECT concept_id, SUM(hits) AS hits, COUNT(DISTINCT document_id) AS documents
            FROM concept_hits WHERE document_id IN ({qmarks})
            GROUP BY concept_id ORDER BY hits DESC""",
        ids,
    ):
        nodes.append({
            "id": r["concept_id"],
            "label": labels.get(r["concept_id"], r["concept_id"]),
            "hits": r["hits"],
            "documents": r["documents"],
            "selected": r["concept_id"] in selected,
        })
    nodes = _score_rows(nodes, len(ids))
    other = [n for n in nodes if not n["selected"]]
    links = []
    for r in db.execute(
        f"""SELECT a.concept_id AS source, b.concept_id AS target,
                   COUNT(DISTINCT a.document_id) AS documents
            FROM concept_hits a
            JOIN concept_hits b ON a.document_id = b.document_id
             AND a.concept_id < b.concept_id
            WHERE a.document_id IN ({qmarks})
            GROUP BY a.concept_id, b.concept_id
            ORDER BY documents DESC LIMIT 40""",
        ids,
    ):
        links.append({
            "source": r["source"], "target": r["target"], "documents": r["documents"],
        })
    return {"nodes": nodes, "links": links, "other": other}


@app.get("/api/entities")
def entities(f: FDep, label: str | None = None):
    db = _db()
    ids = _filtered_ids(db, f)
    if not ids:
        return []
    want = (label or "").upper()
    if want not in {"PERSON", "ORG"}:
        want = None
    qmarks = _in(ids)
    sql = f"""SELECT name, label, document_id, SUM(count) AS count
              FROM entities WHERE document_id IN ({qmarks})"""
    args = list(ids)
    if want:
        sql += " AND label = ?"
        args.append(want)
    sql += " GROUP BY name, label, document_id"
    by_name = {}
    for r in db.execute(sql, args):
        key = (r["name"], r["label"])
        slot = by_name.setdefault(key, {"name": r["name"], "label": r["label"], "count": 0, "docs": set()})
        slot["count"] += r["count"]
        slot["docs"].add(r["document_id"])
    rows = []
    for slot in by_name.values():
        rows.append({
            "name": slot["name"], "label": slot["label"],
            "count": slot["count"], "documents": len(slot["docs"]),
        })
    people = collapse_people([r for r in rows if r["label"] == "PERSON"])
    orgs = collapse_orgs([r for r in rows if r["label"] == "ORG"])
    merged = (people if want != "ORG" else []) + (orgs if want != "PERSON" else [])
    for g in merged:
        docs = set()
        total = 0
        for n in g.get("names") or [g["name"]]:
            slot = by_name.get((n, g["label"]))
            if not slot:
                continue
            docs |= slot["docs"]
            total += slot["count"]
        g["documents"] = len(docs)
        g["count"] = total
    merged = _score_rows(merged, len(ids), hits_key="count")
    merged.sort(key=lambda r: -r["count"])
    return merged[:400]


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


def _qty_clause(ids, units=None, mq=None, value_min=None, value_max=None):
    where = [f"qn.document_id IN ({_in(ids)})"]
    args = list(ids)
    if units:
        where.append("qn.unit IN (" + ",".join("?" * len(units)) + ")")
        args.extend(units)
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
def measurements(f: FDep, mq: str | None = None, value_min: float | None = None,
                 value_max: float | None = None):
    db = _db()
    ids = _filtered_ids(db, f)
    if not ids:
        return []
    clause, args = _qty_clause(ids, units=f.units, mq=mq, value_min=value_min, value_max=value_max)
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
def measurement_hits(f: FDep, mq: str | None = None, value_min: float | None = None,
                     value_max: float | None = None, limit: int = 80):
    db = _db()
    ids = _filtered_ids(db, f)
    if not ids:
        return []
    clause, args = _qty_clause(ids, units=f.units, mq=mq, value_min=value_min, value_max=value_max)
    rows = db.execute(
        f"""SELECT qn.value AS value, qn.unit AS unit, qn.surface AS surface,
                   d.id AS document_id, d.filename AS filename
            FROM quantities qn JOIN documents d ON d.id = qn.document_id
            WHERE {clause} ORDER BY qn.unit, qn.value LIMIT ?""",
        args + [min(limit, 200)],
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/measurements/histogram")
def measurement_histogram(f: FDep, hist_unit: str | None = None, bins: int = 12):
    db = _db()
    ids = _filtered_ids(db, f)
    unit = hist_unit or (f.units[-1] if f.units else None)
    if not unit or not ids:
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


def _filter_dump(f: Filters):
    return {
        "q": f.q,
        "concepts": f.concepts,
        "places": f.places,
        "persons": f.persons,
        "orgs": f.orgs,
        "units": f.units,
        "years": [{"min": a, "max": b} for a, b in f.years],
        "bboxes": f.bboxes,
    }


def _cut_payload(f: Filters):
    return {
        "filters": _filter_dump(f),
        "documents": documents(f),
        "places": places(f),
        "concepts": [c for c in concepts(f) if c.get("hits")],
        "people": entities(f, label="PERSON"),
        "orgs": entities(f, label="ORG"),
        "measurements": measurements(f),
    }


def _csv_bytes(rows, fields):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue().encode("utf-8")


@app.get("/api/export")
def export_cut(f: FDep, fmt: str = "json"):
    payload = _cut_payload(f)
    kind = (fmt or "json").lower()
    if kind == "json":
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=meridian-cut.json"},
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "documents.csv",
            _csv_bytes(payload["documents"], [
                "id", "filename", "path", "mime", "year", "language",
                "word_count", "unique_terms", "ttr", "file_size", "text_size",
            ]),
        )
        zf.writestr(
            "places.csv",
            _csv_bytes(payload["places"], ["name", "lat", "lon", "count", "documents", "score"]),
        )
        zf.writestr(
            "people.csv",
            _csv_bytes(payload["people"], ["name", "count", "documents", "score"]),
        )
        zf.writestr(
            "orgs.csv",
            _csv_bytes(payload["orgs"], ["name", "count", "documents", "score"]),
        )
        zf.writestr(
            "concepts.csv",
            _csv_bytes(payload["concepts"], ["id", "label", "hits", "documents", "score"]),
        )
        zf.writestr(
            "measurements.csv",
            _csv_bytes(payload["measurements"], ["unit", "count", "documents", "min", "max", "avg"]),
        )
        zf.writestr("filters.json", json.dumps(payload["filters"], indent=2).encode("utf-8"))
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=meridian-cut.zip"},
    )


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="ui")


def run(host="127.0.0.1", port=8090):
    import uvicorn
    if not WEB_DIST.exists():
        print("UI not built (web/dist missing). API only.")
        print("  cd web && npm install && npm run build")
    uvicorn.run(app, host=host, port=port, log_level="info")
