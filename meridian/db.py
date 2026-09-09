import json
import sqlite3
from .paths import DB_PATH, ensure_data

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  mime TEXT,
  text TEXT,
  year INTEGER,
  file_size INTEGER,
  text_size INTEGER,
  meta_size INTEGER,
  language TEXT,
  word_count INTEGER,
  unique_terms INTEGER,
  ttr REAL,
  tag_count INTEGER,
  metadata TEXT,
  indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  filename, text, content='documents', content_rowid='id'
);
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  lat REAL,
  lon REAL,
  count INTEGER DEFAULT 1,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
CREATE INDEX IF NOT EXISTS idx_places_doc ON places(document_id);
CREATE TABLE IF NOT EXISTS place_cache (
  name TEXT PRIMARY KEY,
  lat REAL,
  lon REAL,
  display TEXT
);
CREATE TABLE IF NOT EXISTS times (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER,
  surface TEXT,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_times_year ON times(year);
CREATE TABLE IF NOT EXISTS quantities (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL,
  value REAL,
  unit TEXT,
  surface TEXT,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_quantities_unit ON quantities(unit);
CREATE TABLE IF NOT EXISTS concept_hits (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL,
  concept_id TEXT NOT NULL,
  label TEXT NOT NULL,
  hits INTEGER DEFAULT 1,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_concept_hits ON concept_hits(concept_id);
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, filename, text)
  VALUES (new.id, new.filename, new.text);
END;
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, filename, text)
  VALUES('delete', old.id, old.filename, old.text);
END;
"""


def _migrate(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(documents)")}
    for col, spec in (
        ("file_size", "INTEGER"),
        ("text_size", "INTEGER"),
        ("meta_size", "INTEGER"),
        ("language", "TEXT"),
        ("word_count", "INTEGER"),
        ("unique_terms", "INTEGER"),
        ("ttr", "REAL"),
        ("tag_count", "INTEGER"),
        ("metadata", "TEXT"),
    ):
        if col not in cols:
            db.execute(f"ALTER TABLE documents ADD COLUMN {col} {spec}")
            if col == "tag_count":
                # ttr used to store type–token ratio; TTR is text-to-tag.
                db.execute("UPDATE documents SET ttr = NULL")
    tcols = {r[1] for r in db.execute("PRAGMA table_info(times)")}
    if "month" not in tcols:
        db.execute("ALTER TABLE times ADD COLUMN month INTEGER")
    db.execute("CREATE INDEX IF NOT EXISTS idx_times_month ON times(year, month)")
    db.commit()


def connect(path=None):
    ensure_data()
    db = sqlite3.connect(path or DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    db.executescript(TRIGGERS)
    _migrate(db)
    return db


def reset(path=None):
    """Empty the catalog. The GeoNames gazetteer is not the catalog."""
    db = connect(path)
    db.execute("DELETE FROM documents")
    db.commit()
    return db


def insert_document(db, path, filename, mime, text, year, stats=None):
    stats = stats or {}
    meta = stats.get("metadata") or {}
    cur = db.execute(
        """INSERT INTO documents(
             path, filename, mime, text, year,
             file_size, text_size, meta_size, language,
             word_count, unique_terms, ttr, tag_count, metadata
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            path, filename, mime, text, year,
            stats.get("file_size"), stats.get("text_size"), stats.get("meta_size"),
            stats.get("language"), stats.get("word_count"), stats.get("unique_terms"),
            stats.get("ttr"), stats.get("tag_count"), json.dumps(meta, ensure_ascii=False),
        ),
    )
    return cur.lastrowid


def clear_document_annotations(db, doc_id):
    for table in ("places", "times", "quantities", "concept_hits"):
        db.execute(f"DELETE FROM {table} WHERE document_id=?", (doc_id,))


def document_id_for_path(db, path):
    row = db.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()
    return row["id"] if row else None
