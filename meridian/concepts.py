import re
from pathlib import Path
import yaml
from .paths import CONCEPTS_PATH


def load(path=None):
    p = Path(path or CONCEPTS_PATH)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or []
    out = []
    for row in data:
        aliases = [a for a in ([row.get("label")] + list(row.get("aliases") or [])) if a]
        out.append({
            "id": row["id"],
            "label": row.get("label") or row["id"],
            "aliases": aliases,
        })
    return out


def save(concepts, path=None):
    p = Path(path or CONCEPTS_PATH)
    dump = [
        {"id": c["id"], "label": c["label"], "aliases": [a for a in c["aliases"] if a != c["label"]]}
        for c in concepts
    ]
    p.write_text(yaml.safe_dump(dump, sort_keys=False, allow_unicode=True))


def match(text, concepts=None):
    """Return [{id, label, hits}] for concepts whose aliases appear in text."""
    if not text:
        return []
    blob = text.lower()
    hits = []
    for c in (concepts or load()):
        n = 0
        for alias in c["aliases"]:
            if not alias:
                continue
            n += len(re.findall(r"\b" + re.escape(alias.lower()) + r"\b", blob))
        if n:
            hits.append({"id": c["id"], "label": c["label"], "hits": n})
    return hits
