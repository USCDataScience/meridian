<template>
  <section>
    <div class="grid">
      <div class="card">
        <h3>MIME types</h3>
        <div ref="mimeEl" class="chart"></div>
      </div>
      <div class="card">
        <h3>Languages</h3>
        <div ref="langEl" class="chart"></div>
      </div>
      <div class="card wide">
        <h3>Extraction yield</h3>
        <table class="nums">
          <thead><tr><th></th><th>Max</th><th>Average</th><th>Sum</th></tr></thead>
          <tbody>
            <tr>
              <th><span class="explain" data-tip="Files in the current filter set.">Documents</span></th>
              <td colspan="3">{{ stats.documents }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Bytes on disk before extraction.">File size</span></th>
              <td>{{ bytes(stats.file_size?.max) }}</td>
              <td>{{ bytes(stats.file_size?.avg) }}</td>
              <td>{{ bytes(stats.file_size?.sum) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="UTF-8 bytes of Tika-extracted text.">Extracted text</span></th>
              <td>{{ bytes(stats.text_size?.max) }}</td>
              <td>{{ bytes(stats.text_size?.avg) }}</td>
              <td>{{ bytes(stats.text_size?.sum) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Serialized Tika metadata size (keys/values kept after indexing).">Metadata size</span></th>
              <td>{{ bytes(stats.meta_size?.max) }}</td>
              <td>{{ bytes(stats.meta_size?.avg) }}</td>
              <td>{{ bytes(stats.meta_size?.sum) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="extracted text bytes / file bytes. PDFs are mostly binary, so this is often a few percent.">Text yield</span></th>
              <td colspan="3">{{ pct(stats.text_yield_avg) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="metadata bytes / file bytes.">Metadata yield</span></th>
              <td colspan="3">{{ pct(stats.meta_yield_avg) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Unique terms ÷ tokens in the extracted text. Higher means more varied vocabulary; lower means more repetition.">Type–token ratio</span></th>
              <td colspan="3">{{ stats.type_token_avg != null ? stats.type_token_avg.toFixed(3) : '—' }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Text-to-tag ratio: visible text characters ÷ markup tags in Tika XHTML. Higher means more text per tag (content-heavy); lower means denser markup.">TTR</span></th>
              <td colspan="3">{{ stats.ttr_avg != null ? stats.ttr_avg.toFixed(2) : '—' }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Word-like tokens ([A-Za-z][A-Za-z0-9']+) in extracted text.">Tokens</span></th>
              <td>{{ fmt(stats.word_count?.max) }}</td>
              <td>{{ fmt(stats.word_count?.avg) }}</td>
              <td>{{ fmt(stats.word_count?.sum) }}</td>
            </tr>
            <tr>
              <th><span class="explain" data-tip="Distinct tokens, case-folded. The numerator of type–token ratio.">Unique terms</span></th>
              <td>{{ fmt(stats.unique_terms?.max) }}</td>
              <td>{{ fmt(stats.unique_terms?.avg) }}</td>
              <td>{{ fmt(stats.unique_terms?.sum) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <table class="docs">
      <thead>
        <tr>
          <th>File</th>
          <th><span class="explain" data-tip="Tika Content-Type. Empty means Tika returned no type (parse failed).">MIME</span></th>
          <th><span class="explain" data-tip="Bytes on disk.">Size</span></th>
          <th><span class="explain" data-tip="Extracted text bytes / file bytes.">Text %</span></th>
          <th><span class="explain" data-tip="Metadata bytes / file bytes.">Meta %</span></th>
          <th><span class="explain" data-tip="Unique terms / tokens.">Type–token</span></th>
          <th><span class="explain" data-tip="TTR = text-to-tag ratio: text characters / XHTML tags from Tika.">TTR</span></th>
          <th><span class="explain" data-tip="Language from Tika metadata, or English if the text looks like English.">Lang</span></th>
          <th><span class="explain" data-tip="Most common extracted year in the document, not necessarily publication year.">Year</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in documents" :key="d.id" class="click" @click="$emit('open', d.id)">
          <td>{{ d.filename }}</td>
          <td class="muted">{{ d.mime }}</td>
          <td>{{ bytes(d.file_size) }}</td>
          <td>{{ pct(d.text_yield) }}</td>
          <td>{{ pct(d.meta_yield) }}</td>
          <td>{{ d.type_token != null ? d.type_token.toFixed(3) : '—' }}</td>
          <td>{{ d.ttr != null ? d.ttr.toFixed(2) : '—' }}</td>
          <td>{{ d.language || '—' }}</td>
          <td>{{ d.year || '—' }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!documents.length" class="muted">No documents. Run <code>meridian index ./demo</code>.</p>

    <article v-if="detail" class="detail">
      <h2>{{ detail.filename }}</h2>
      <p class="muted">{{ detail.path }}</p>
      <div class="kpis">
        <span class="explain" data-tip="Extracted text bytes / file bytes."><strong>{{ pct(detail.text_yield) }}</strong> text yield</span>
        <span class="explain" data-tip="Metadata bytes / file bytes."><strong>{{ pct(detail.meta_yield) }}</strong> metadata yield</span>
        <span class="explain" data-tip="Word-like tokens in extracted text."><strong>{{ fmt(detail.word_count) }}</strong> tokens</span>
        <span class="explain" data-tip="Distinct tokens. Numerator of type–token ratio."><strong>{{ fmt(detail.unique_terms) }}</strong> unique</span>
        <span class="explain" data-tip="Unique terms / tokens."><strong>{{ detail.type_token != null ? detail.type_token.toFixed(3) : '—' }}</strong> type–token</span>
        <span class="explain" data-tip="Text-to-tag ratio: text characters / Tika XHTML tags."><strong>{{ detail.ttr != null ? detail.ttr.toFixed(2) : '—' }}</strong> TTR</span>
      </div>
      <div class="tabs">
        <button v-for="t in tabs" :key="t" :class="{ active: tab === t }" @click="tab = t">{{ t }}</button>
      </div>
      <div v-if="tab === 'Text'" class="text">
        <pre>{{ detail.text }}</pre>
      </div>
      <div v-if="tab === 'Metadata'">
        <table class="meta">
          <tbody>
            <tr v-for="(v, k) in detail.metadata" :key="k"><th>{{ k }}</th><td>{{ v }}</td></tr>
          </tbody>
        </table>
        <p v-if="!Object.keys(detail.metadata || {}).length" class="muted">No Tika metadata stored.</p>
      </div>
      <div v-if="tab === 'Extractions'" class="grid">
        <div>
          <h3>Places</h3>
          <div ref="placeEl" class="chart"></div>
        </div>
        <div>
          <h3>Years</h3>
          <div ref="yearEl" class="chart"></div>
        </div>
        <div class="wide">
          <p><strong>Concepts:</strong> {{ (detail.concepts || []).map(c => c.label + ' (' + c.hits + ')').join(', ') || '—' }}</p>
          <p><strong>Times:</strong> {{ (detail.times || []).slice(0, 20).map(t => t.month ? t.year + '-' + String(t.month).padStart(2,'0') : t.year).join(', ') }}</p>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { barChart, paint, pieChart } from '../charts.js'

const props = defineProps({
  documents: { type: Array, default: () => [] },
  stats: { type: Object, default: () => ({}) },
  detail: { type: Object, default: null }
})
defineEmits(['open'])

const mimeEl = ref(null)
const langEl = ref(null)
const placeEl = ref(null)
const yearEl = ref(null)
const tab = ref('Text')
const tabs = ['Text', 'Metadata', 'Extractions']

function bytes(n) {
  if (n == null || Number.isNaN(n)) return '—'
  if (n > 1048576) return (n / 1048576).toFixed(2) + ' MB'
  if (n > 1024) return (n / 1024).toFixed(1) + ' KB'
  return Math.round(n) + ' B'
}
function fmt(n) {
  if (n == null || Number.isNaN(n)) return '—'
  const x = Number(n)
  if (Math.abs(x) >= 1000) return Math.round(x).toLocaleString()
  return Number.isInteger(x) ? String(x) : x.toFixed(1)
}
function pct(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return (n * 100).toFixed(1) + '%'
}

function draw() {
  paint(() => {
    pieChart(mimeEl.value, (props.stats.mime || []).map(d => ({
      label: d.mime || '(unparsed)',
      count: d.count
    })))
    pieChart(langEl.value, (props.stats.languages || []).map(d => ({ label: d.language, count: d.count })))
    if (props.detail) {
      barChart(placeEl.value, (props.detail.places || []).slice(0, 12).map(p => ({ label: p.name, count: p.count })))
      const years = {}
      ;(props.detail.times || []).forEach(t => { years[t.year] = (years[t.year] || 0) + 1 })
      barChart(yearEl.value, Object.entries(years).map(([label, count]) => ({ label, count })).slice(-16))
    }
  })
}

onMounted(draw)
watch(() => [props.stats, props.detail, tab.value], draw, { deep: true })
</script>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.2rem; }
.wide { grid-column: 1 / -1; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem 1rem; }
.chart { width: 100%; min-height: 8rem; }
.nums { width: 100%; border-collapse: collapse; }
.nums th, .nums td { padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--line); text-align: right; }
.nums th:first-child, .nums td:first-child { text-align: left; }
.docs { width: 100%; border-collapse: collapse; }
.docs th { text-align: left; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.docs td, .docs th { padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--line); }
.click { cursor: pointer; }
.click:hover { background: #efe8d8; }
.muted { color: var(--muted); }
.explain { border-bottom: 1px dotted var(--muted); cursor: help; }
.explain:hover::after, .explain:focus::after {
  content: attr(data-tip);
  position: absolute;
  z-index: 40;
  max-width: 18rem;
  margin-top: 1.4rem;
  background: #12202a;
  color: #fffdf8;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  white-space: normal;
  box-shadow: 0 8px 24px rgba(18,32,42,.28);
  border: 1px solid #c9a227;
}
.nums th, .docs th, .kpis span { position: relative; }
.detail { margin-top: 1.2rem; background: var(--card); border: 1px solid var(--line); padding: 1rem; border-radius: 8px; }
.detail pre { white-space: pre-wrap; font-size: 0.85rem; max-height: 28rem; overflow: auto; }
.kpis { display: flex; flex-wrap: wrap; gap: 1rem; margin: 0.6rem 0; color: var(--muted); }
.kpis strong { color: var(--sea); }
.tabs { display: flex; gap: 0.4rem; margin: 0.8rem 0; }
.tabs button { background: none; border: 1px solid var(--line); padding: 0.25rem 0.7rem; border-radius: 4px; cursor: pointer; }
.tabs button.active { background: var(--sea); color: #fff; border-color: var(--sea); }
.meta { width: 100%; }
.meta th { text-align: left; width: 14rem; color: var(--muted); vertical-align: top; padding: 0.25rem 0.5rem; }
.meta td { padding: 0.25rem 0.5rem; }
h3 { margin: 0 0 0.4rem; font-size: 0.95rem; color: var(--sea); }
@media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
</style>
