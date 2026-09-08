"""Tika + spaCy + quantulum3. No sidecars."""

import re
from collections import Counter

_nlp = None
YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")


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
    return text.strip(), mime, meta


def years_from_text(text, meta=None):
    found = [int(y) for y in YEAR.findall(text or "")]
    if meta:
        for key in ("Creation-Date", "created", "date", "dcterms:created"):
            val = meta.get(key)
            if not val:
                continue
            if isinstance(val, list):
                val = val[0]
            found.extend(int(y) for y in YEAR.findall(str(val)))
    found = [y for y in found if 1500 <= y <= 2100]
    return found


def analyze(text):
    """NER places/dates and keep a short text window for spaCy."""
    doc = nlp()((text or "")[:80000])
    places = Counter()
    date_surfaces = []
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC"):
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
