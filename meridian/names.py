"""Collapse PERSON/ORG surface variants (C. Mattmann ~ Chris A. Mattmann)."""

import re
from collections import defaultdict

_PUNCT = re.compile(r"[.']")
_NON = re.compile(r"[^a-z0-9\s-]")


def tokens(name):
    s = _PUNCT.sub(" ", (name or "").lower())
    s = _NON.sub(" ", s)
    return [t for t in s.split() if t]


def person_key(name):
    toks = tokens(name)
    if not toks:
        return None
    last = toks[-1]
    if len(toks) == 1:
        return (last, "")
    return (last, toks[0][0])


def org_key(name):
    toks = tokens(name)
    if not toks:
        return None
    if toks[0] == "the" and len(toks) > 1:
        toks = toks[1:]
    return " ".join(toks)


def _pick_display(rows):
    return max(
        rows,
        key=lambda r: (r.get("count") or 0, len(tokens(r["name"])), len(r["name"])),
    )["name"]


def collapse_people(rows):
    by_last = defaultdict(list)
    for row in rows:
        key = person_key(row["name"])
        if not key:
            continue
        last, ini = key
        by_last[last].append((ini, row))
    out = []
    for last, items in by_last.items():
        initials = {ini for ini, _ in items if ini}
        buckets = defaultdict(list)
        leftover = []
        for ini, row in items:
            if not ini:
                leftover.append(row)
            else:
                buckets[ini].append(row)
        if len(initials) == 1 and leftover:
            buckets[next(iter(initials))].extend(leftover)
            leftover = []
        for ini, group in buckets.items():
            out.append(_bundle(group))
        if leftover:
            out.append(_bundle(leftover))
    out.sort(key=lambda r: -r["count"])
    return out


def collapse_orgs(rows):
    buckets = defaultdict(list)
    for row in rows:
        key = org_key(row["name"])
        if not key:
            continue
        buckets[key].append(row)
    out = [_bundle(group) for group in buckets.values()]
    out.sort(key=lambda r: -r["count"])
    return out


def _bundle(group):
    names = []
    seen = set()
    for r in group:
        n = r["name"]
        k = n.lower()
        if k in seen:
            continue
        seen.add(k)
        names.append(n)
    return {
        "name": _pick_display(group),
        "names": names,
        "label": group[0].get("label") or "PERSON",
        "count": sum(r.get("count") or 0 for r in group),
        "documents": sum(r.get("documents") or 0 for r in group),
    }


def aliases_for(all_names, query_names, kind="PERSON"):
    """Expand query surfaces to every catalog name in the same collapsed group."""
    seen_in = set()
    names = []
    for n in list(all_names) + list(query_names):
        k = (n or "").lower()
        if not k or k in seen_in:
            continue
        seen_in.add(k)
        names.append(n)
    rows = [{"name": n, "count": 0, "documents": 0, "label": kind} for n in names]
    groups = collapse_people(rows) if kind == "PERSON" else collapse_orgs(rows)
    want = {n.lower() for n in query_names}
    out = []
    seen = set()
    for g in groups:
        aliases = g["names"]
        if want & {a.lower() for a in aliases}:
            for a in aliases:
                if a.lower() not in seen:
                    seen.add(a.lower())
                    out.append(a)
    for n in query_names:
        if n.lower() not in seen:
            out.append(n)
            seen.add(n.lower())
    return out


def idf_score(hits, df, n_docs):
    import math
    if not hits or not df or not n_docs:
        return 0.0
    return (1.0 + math.log(hits)) * math.log(1.0 + n_docs / df)
