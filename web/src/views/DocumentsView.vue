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
            <tr><th>Documents</th><td colspan="3">{{ stats.documents }}</td></tr>
            <tr>
              <th>File size</th>
              <td>{{ bytes(stats.file_size?.max) }}</td>
              <td>{{ bytes(stats.file_size?.avg) }}</td>
              <td>{{ bytes(stats.file_size?.sum) }}</td>
            </tr>
            <tr>
              <th>Extracted text</th>
              <td>{{ bytes(stats.text_size?.max) }}</td>
              <td>{{ bytes(stats.text_size?.avg) }}</td>
              <td>{{ bytes(stats.text_size?.sum) }}</td>
            </tr>
            <tr>
              <th>Metadata size</th>
              <td>{{ bytes(stats.meta_size?.max) }}</td>
              <td>{{ bytes(stats.meta_size?.avg) }}</td>
              <td>{{ bytes(stats.meta_size?.sum) }}</td>
            </tr>
            <tr>
              <th>Text yield (text / file)</th>
              <td colspan="3">{{ pct(stats.text_yield_avg) }}</td>
            </tr>
            <tr>
              <th>Metadata yield (meta / file)</th>
              <td colspan="3">{{ pct(stats.meta_yield_avg) }}</td>
            </tr>
            <tr>
              <th>Type–token ratio</th>
              <td colspan="3">{{ stats.ttr_avg != null ? stats.ttr_avg.toFixed(3) : '—' }}</td>
            </tr>
            <tr>
              <th>Tokens</th>
              <td>{{ fmt(stats.word_count?.max) }}</td>
              <td>{{ fmt(stats.word_count?.avg) }}</td>
              <td>{{ fmt(stats.word_count?.sum) }}</td>
            </tr>
            <tr>
              <th>Unique terms</th>
              <td>{{ fmt(stats.unique_terms?.max) }}</td>
              <td>{{ fmt(stats.unique_terms?.avg) }}</td>
              <td>{{ fmt(stats.unique_terms?.sum) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="hint">Same yield table as Polar Deep Insights Stats — text and metadata over file size, plus TTR from the content-detection lecture.</p>
      </div>
    </div>

    <table class="docs">
      <thead>
        <tr>
          <th>File</th><th>MIME</th><th>Size</th><th>Text %</th><th>Meta %</th>
          <th>TTR</th><th>Lang</th><th>Year</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in documents" :key="d.id" class="click" @click="$emit('open', d.id)">
          <td>{{ d.filename }}</td>
          <td class="muted">{{ d.mime }}</td>
          <td>{{ bytes(d.file_size) }}</td>
          <td>{{ pct(d.text_yield) }}</td>
          <td>{{ pct(d.meta_yield) }}</td>
          <td>{{ d.ttr != null ? d.ttr.toFixed(3) : '—' }}</td>
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
        <span><strong>{{ pct(detail.text_yield) }}</strong> text yield</span>
        <span><strong>{{ pct(detail.meta_yield) }}</strong> metadata yield</span>
        <span><strong>{{ fmt(detail.word_count) }}</strong> tokens</span>
        <span><strong>{{ fmt(detail.unique_terms) }}</strong> unique</span>
        <span><strong>{{ detail.ttr != null ? detail.ttr.toFixed(3) : '—' }}</strong> TTR</span>
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
import { nextTick, onUpdated, ref, watch } from 'vue'
import { barChart, pieChart } from '../charts.js'

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
  pieChart(mimeEl.value, (props.stats.mime || []).map(d => ({ label: d.mime, count: d.count })))
  pieChart(langEl.value, (props.stats.languages || []).map(d => ({ label: d.language, count: d.count })))
  if (props.detail) {
    barChart(placeEl.value, (props.detail.places || []).slice(0, 12).map(p => ({ label: p.name, count: p.count })))
    const years = {}
    ;(props.detail.times || []).forEach(t => { years[t.year] = (years[t.year] || 0) + 1 })
    barChart(yearEl.value, Object.entries(years).map(([label, count]) => ({ label, count })).slice(-16))
  }
}

watch(() => [props.stats, props.detail, tab.value], () => nextTick(draw), { deep: true })
onUpdated(draw)
</script>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.2rem; }
.wide { grid-column: 1 / -1; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem 1rem; }
.chart { min-height: 8rem; }
.nums { width: 100%; border-collapse: collapse; }
.nums th, .nums td { padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--line); text-align: right; }
.nums th:first-child, .nums td:first-child { text-align: left; }
.docs { width: 100%; border-collapse: collapse; }
.docs th { text-align: left; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.docs td, .docs th { padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--line); }
.click { cursor: pointer; }
.click:hover { background: #efe8d8; }
.muted { color: var(--muted); }
.hint { color: var(--muted); font-size: 0.85rem; }
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
