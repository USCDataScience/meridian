<template>
  <section>
    <div class="search">
      <input v-model="mq" placeholder="Search unit or surface (kelvin, km, 11.5 h)" @keyup.enter="run"/>
      <input v-model="valueMin" type="number" placeholder="Min value" @change="run"/>
      <input v-model="valueMax" type="number" placeholder="Max value" @change="run"/>
      <button class="go" @click="run">Search measurements</button>
      <button @click="clear">Clear</button>
    </div>
    <div class="grid">
      <div class="card">
        <h3>Units (share)</h3>
        <div ref="pieEl" class="chart"></div>
      </div>
      <div class="card">
        <h3>Units (count)</h3>
        <div ref="barEl" class="chart"></div>
      </div>
    </div>
    <div v-if="hist.length" class="card">
      <h3>Histogram · {{ unit }}</h3>
      <div ref="histEl" class="chart"></div>
    </div>
    <table>
      <thead>
        <tr><th>Unit</th><th>Count</th><th>Docs</th><th>Min</th><th>Max</th><th>Average</th></tr>
      </thead>
      <tbody>
        <tr v-for="m in measures" :key="m.unit" class="click" @click="pick(m.unit)">
          <td>{{ m.unit }}</td>
          <td>{{ m.count }}</td>
          <td>{{ m.documents }}</td>
          <td>{{ n(m.min) }}</td>
          <td>{{ n(m.max) }}</td>
          <td>{{ n(m.avg) }}</td>
        </tr>
      </tbody>
    </table>
    <h3 v-if="hits.length">Matching extractions</h3>
    <table v-if="hits.length">
      <thead><tr><th>Value</th><th>Unit</th><th>Surface</th><th>File</th></tr></thead>
      <tbody>
        <tr v-for="(h, i) in hits" :key="i">
          <td>{{ n(h.value) }}</td>
          <td>{{ h.unit }}</td>
          <td class="muted">{{ h.surface }}</td>
          <td>{{ h.filename }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { barChart, histogram, paint, pieChart } from '../charts.js'
import { get } from '../api.js'

const props = defineProps({
  measures: { type: Array, default: () => [] },
  filters: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['unit'])

const pieEl = ref(null)
const barEl = ref(null)
const histEl = ref(null)
const mq = ref('')
const valueMin = ref('')
const valueMax = ref('')
const unit = ref('')
const hist = ref([])
const hits = ref([])

function n(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(2)
}

async function run() {
  const extra = {
    ...props.filters,
    mq: mq.value,
    value_min: valueMin.value,
    value_max: valueMax.value,
    unit: unit.value || props.filters.unit
  }
  hits.value = await get('/api/measurements/hits', extra)
  if (unit.value) hist.value = await get('/api/measurements/histogram', { ...props.filters, unit: unit.value })
  else hist.value = []
  nextTick(draw)
}

function clear() {
  mq.value = valueMin.value = valueMax.value = ''
  unit.value = ''
  hist.value = []
  hits.value = []
  emit('unit', '')
}

async function pick(u) {
  unit.value = u
  emit('unit', u)
  await run()
}

function draw() {
  paint(() => {
    const rows = props.measures.slice(0, 12).map(m => ({ label: m.unit, count: m.count }))
    pieChart(pieEl.value, rows)
    barChart(barEl.value, rows, { onClick: d => pick(d.label) })
    histogram(histEl.value, hist.value)
  })
}

onMounted(draw)
watch(() => props.measures, draw, { deep: true })
</script>

<style scoped>
.search { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
.search input { padding: 0.35rem 0.5rem; border: 1px solid var(--line); border-radius: 4px; }
.go { background: var(--sea); color: #fff; border: none; padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 1rem; }
.chart { width: 100%; min-height: 10rem; }
table { width: 100%; border-collapse: collapse; margin-top: 0.6rem; }
th { text-align: left; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
td, th { padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--line); }
.click { cursor: pointer; }
.click:hover { background: #efe8d8; }
.muted { color: var(--muted); }
h3 { margin: 0.8rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
@media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
</style>
