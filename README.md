Meridian
========

Point it at a corpus. Cut it on **concept, place, and time**.

Tika extracts text. spaCy finds names and dates. quantulum3 finds quantities.
Places are geocoded once and cached. Concepts live in `concepts.yaml`.
Everything lands in SQLite. A Vue 3 UI filters the three axes together.

No Docker. No Elasticsearch. No GeoTopic or GROBID sidecars.

Needs **Java 11+** (Tika), **Python 3.10+**, and **Node 18+** to build the UI.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m spacy download en_core_web_sm
cd web && npm install && npm run build && cd ..

bin/meridian index ./demo
bin/meridian serve
```

Open http://127.0.0.1:8090/

The Documents view reports MIME, extraction yield (text/file, metadata/file),
type–token ratio, Tika metadata, and extracted text. Map is a D3 bubble map.
Timeline is a year×month heatmap. Measurements are pies, histograms, and a
search over unit/surface/value.

```bash
bin/meridian index ./papers ./notes
bin/meridian index ./demo --no-geo   # skip Nominatim if you are offline
bin/meridian reset --yes
```

`bin/meridian` uses `.venv` when it exists. The concept editor in the UI
appends to `concepts.yaml` and rematches the catalog.

Formerly Polar Deep Insights. Polar TREC was the first corpus, not the product.

Work of [Chris Mattmann](https://github.com/chrismattmann) and [Mattmann.AI](https://mattmann.ai).
[IRDS](https://irds.usc.edu), University of Southern California.
Apache License 2.0.
