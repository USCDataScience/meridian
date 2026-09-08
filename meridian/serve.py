from pathlib import Path
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
        where.append("p.name = ?")
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


@app.get("/api/stats")
def stats():
    db = _db()
    n = db.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    return {
        "documents": n,
        "places": db.execute("SELECT COUNT(DISTINCT name) c FROM places").fetchone()["c"],
        "years": db.execute("SELECT COUNT(DISTINCT year) c FROM times").fetchone()["c"],
        "concepts": db.execute("SELECT COUNT(DISTINCT concept_id) c FROM concept_hits").fetchone()["c"],
        "quantities": db.execute("SELECT COUNT(*) c FROM quantities").fetchone()["c"],
    }


@app.get("/api/documents")
def documents(q: str | None = None, concept: str | None = None, place: str | None = None,
              year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    qmarks = ",".join("?" * len(ids))
    rows = db.execute(
        f"SELECT id, path, filename, mime, year FROM documents WHERE id IN ({qmarks}) ORDER BY filename",
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    db = _db()
    row = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    d = dict(row)
    d["places"] = [dict(r) for r in db.execute(
        "SELECT name, lat, lon, count FROM places WHERE document_id=?", (doc_id,))]
    d["years"] = [r["year"] for r in db.execute(
        "SELECT DISTINCT year FROM times WHERE document_id=? ORDER BY year", (doc_id,))]
    d["concepts"] = [dict(r) for r in db.execute(
        "SELECT concept_id, label, hits FROM concept_hits WHERE document_id=?", (doc_id,))]
    d["quantities"] = [dict(r) for r in db.execute(
        "SELECT value, unit, surface FROM quantities WHERE document_id=? LIMIT 50", (doc_id,))]
    d["text"] = (d.get("text") or "")[:4000]
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
        return []
    qmarks = ",".join("?" * len(ids))
    rows = db.execute(
        f"""SELECT year, COUNT(DISTINCT document_id) AS count
            FROM times WHERE document_id IN ({qmarks})
            GROUP BY year ORDER BY year""",
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


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


@app.get("/api/measurements")
def measurements(q: str | None = None, concept: str | None = None, place: str | None = None,
                 year_min: int | None = None, year_max: int | None = None, unit: str | None = None):
    db = _db()
    ids = _filtered_ids(db, q, concept, place, year_min, year_max, unit)
    if not ids:
        return []
    qmarks = ",".join("?" * len(ids))
    rows = db.execute(
        f"""SELECT unit, COUNT(*) AS count, AVG(value) AS avg
            FROM quantities WHERE document_id IN ({qmarks}) AND unit IS NOT NULL AND unit != ''
            GROUP BY unit ORDER BY count DESC LIMIT 40""",
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="ui")


def run(host="127.0.0.1", port=8090):
    import uvicorn
    if not WEB_DIST.exists():
        print("UI not built (web/dist missing). API only.")
        print("  cd web && npm install && npm run build")
    uvicorn.run(app, host=host, port=port, log_level="info")
