"""Tika + spaCy + quantulum3. No sidecars."""

import json
import re
from collections import Counter
from pathlib import Path

_nlp = None
YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9']{1,}")
SKIP_META = re.compile(
    r"(X-TIKA|X-Parsed|Embedded|ResourceName|Content-MD5|X-TIKA:)",
    re.I,
)
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
MONTH_YEAR = re.compile(rf"\b({MONTH_RE})\.?\s+(\d{{4}})\b", re.I)
YEAR_MONTH = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})[-/](0?[1-9]|1[0-2])\b")
ISO_DATE = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})-(\d{2})-(\d{2})\b")


def nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError as e:
            raise SystemExit(
                "spaCy model en_core_web_sm is not installed.\n"
                "  python -m spacy download en_core_web_sm"
            ) from e
    return _nlp


TAG = re.compile(r"<[^>]+>")


def tika_parse(path):
    from tika import parser
    parsed = parser.from_file(str(path))
    meta = parsed.get("metadata") or {}
    text = parsed.get("content") or ""
    if isinstance(text, list):
        text = "\n".join(text)
    mime = meta.get("Content-Type") or meta.get("content-type") or ""
    if isinstance(mime, list):
        mime = mime[0]
    mime = mime.split(";")[0].strip()
    xhtml = None
    try:
        xml_parsed = parser.from_file(str(path), xmlContent=True)
        raw = xml_parsed.get("content") or ""
        if isinstance(raw, list):
            raw = "\n".join(raw)
        xhtml = raw or None
    except Exception:
        xhtml = None
    return text.strip(), mime, meta, xhtml


def text_to_tag_ratio(xhtml):
    """Text-to-tag ratio: visible text characters / number of markup tags (Tika XHTML)."""
    if not xhtml or "<" not in xhtml:
        return None, 0
    tags = TAG.findall(xhtml)
    n_tags = len(tags)
    if not n_tags:
        return None, 0
    text = TAG.sub(" ", xhtml)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, n_tags
    return len(text) / n_tags, n_tags


def _meta_str(meta, key):
    val = (meta or {}).get(key)
    if val is None:
        return ""
    if isinstance(val, list):
        val = val[0]
    return str(val)


def flatten_meta(meta, limit=60):
    out = {}
    for k, v in (meta or {}).items():
        key = str(k)
        if SKIP_META.search(key):
            continue
        if isinstance(v, list):
            v = "; ".join(str(x) for x in v[:8])
        s = str(v).strip()
        if not s or s in {"[]", "null"}:
            continue
        if len(s) > 400:
            s = s[:400] + "…"
        out[key] = s
        if len(out) >= limit:
            break
    return out


def language_of(meta, text=None):
    for key in ("language", "Content-Language", "dc:language", "Content-Language-s"):
        val = _meta_str(meta, key)
        if val:
            return val.split("-")[0].split("_")[0].lower()[:12]
    blob = (text or "").lower()
    if blob.count(" the ") >= 8 and blob.count(" of ") >= 4:
        return "en"
    return None


def text_stats(text, path=None, meta=None, xhtml=None):
    blob = text or ""
    tokens = TOKEN.findall(blob)
    words = [t.lower() for t in tokens]
    unique = set(words)
    file_size = Path(path).stat().st_size if path and Path(path).exists() else 0
    text_size = len(blob.encode("utf-8", errors="ignore"))
    flat = flatten_meta(meta)
    meta_size = len(json.dumps(flat, ensure_ascii=False).encode("utf-8"))
    n = len(words)
    ttr, tag_count = text_to_tag_ratio(xhtml)
    return {
        "file_size": file_size,
        "text_size": text_size,
        "meta_size": meta_size,
        "language": language_of(meta, blob),
        "word_count": n,
        "unique_terms": len(unique),
        "type_token": (len(unique) / n) if n else None,
        "ttr": ttr,
        "tag_count": tag_count,
        "metadata": flat,
        "text_yield": (text_size / file_size) if file_size else None,
        "meta_yield": (meta_size / file_size) if file_size else None,
    }


def years_from_text(text, meta=None):
    found = [int(y) for y in YEAR.findall(text or "")]
    if meta:
        for key in ("Creation-Date", "created", "date", "dcterms:created", "dcterms:modified"):
            found.extend(int(y) for y in YEAR.findall(_meta_str(meta, key)))
    return [y for y in found if 1500 <= y <= 2100]


def _add_time(out, year, month, surface):
    if year is None or not (1500 <= year <= 2100):
        return
    if month is not None and not (1 <= month <= 12):
        month = None
    out.append({"year": year, "month": month, "surface": (surface or str(year))[:80]})


def times_from_text(text, meta=None, date_surfaces=None):
    """Year and optional month from text, DATE entities, and Tika dates."""
    out = []
    blob = text or ""
    for y in years_from_text(blob, meta):
        _add_time(out, y, None, str(y))
    for m in MONTH_YEAR.finditer(blob):
        _add_time(out, int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")], m.group(0))
    for m in YEAR_MONTH.finditer(blob):
        _add_time(out, int(m.group(1)), int(m.group(2)), m.group(0))
    for m in ISO_DATE.finditer(blob):
        _add_time(out, int(m.group(1)), int(m.group(2)), m.group(0))
    for surface in date_surfaces or []:
        s = surface or ""
        m = MONTH_YEAR.search(s)
        if m:
            _add_time(out, int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")], s)
            continue
        m = ISO_DATE.search(s) or YEAR_MONTH.search(s)
        if m:
            _add_time(out, int(m.group(1)), int(m.group(2)), s)
            continue
        ys = YEAR.findall(s)
        if ys:
            _add_time(out, int(ys[0]), None, s)
    if meta:
        for key in ("Creation-Date", "created", "dcterms:created", "modified", "dcterms:modified"):
            val = _meta_str(meta, key)
            iso = ISO_DATE.search(val)
            if iso:
                _add_time(out, int(iso.group(1)), int(iso.group(2)), val)
    # unique (year, month, surface)
    seen = set()
    uniq = []
    for t in out:
        key = (t["year"], t["month"], t["surface"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    return uniq


def analyze(text):
    """NER places/dates and keep a short text window for spaCy."""
    doc = nlp()((text or "")[:80000])
    places = Counter()
    date_surfaces = []
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC"):
            name = " ".join(ent.text.split())
            if name.lower().startswith("the "):
                name = name[4:]
            if len(name) > 1:
                places[name] += 1
        elif ent.label_ == "DATE":
            date_surfaces.append(ent.text)
    return places, date_surfaces


def quantities(text):
    try:
        from quantulum3 import parser as qp
    except ImportError:
        return []
    out = []
    try:
        parsed = qp.parse((text or "")[:40000])
    except Exception:
        return []
    for q in parsed:
        unit = ""
        if q.unit:
            unit = q.unit.name or str(q.unit)
        if not unit or unit.lower() in {"dimensionless", "dimensionless quantity", "unk"}:
            continue
        if len(unit.split()) > 2:
            continue
        out.append({
            "value": float(q.value) if q.value is not None else None,
            "unit": unit,
            "surface": q.surface,
        })
    return out
