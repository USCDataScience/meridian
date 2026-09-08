<template>
  <div class="shell">
    <header class="mast">
      <div class="brand">
        <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="12" fill="none" stroke="currentColor" stroke-width="2"/>
          <line x1="16" y1="4" x2="16" y2="28" stroke="#c9a227" stroke-width="2"/>
        </svg>
        <div>
          <h1>Meridian</h1>
          <p>concept · place · time</p>
        </div>
      </div>
      <nav>
        <button v-for="v in views" :key="v.id" :class="{ active: view === v.id }" @click="view = v.id">{{ v.label }}</button>
      </nav>
    </header>

    <section class="filters">
      <input v-model="filters.q" placeholder="Search text" @keyup.enter="reload"/>
      <select v-model="filters.concept" @change="reload">
        <option value="">All concepts</option>
        <option v-for="c in conceptList" :key="c.id" :value="c.id">{{ c.label }}</option>
      </select>
      <select v-model="filters.place" @change="reload">
        <option value="">All places</option>
        <option v-for="p in placeNames" :key="p" :value="p">{{ p }}</option>
      </select>
      <input v-model="filters.year_min" type="number" placeholder="From year" @change="reload"/>
      <input v-model="filters.year_max" type="number" placeholder="To year" @change="reload"/>
      <select v-model="filters.unit" @change="reload">
        <option value="">All units</option>
        <option v-for="m in unitOptions" :key="m.unit" :value="m.unit">{{ m.unit }}</option>
      </select>
      <button class="go" @click="reload">Apply</button>
      <button @click="clearFilters">Clear</button>
      <span v-if="activeFilter" class="chip">{{ activeFilter }}</span>
    </section>

    <section class="stats" v-if="stats">
      <div><strong>{{ stats.documents }}</strong> documents</div>
      <div><strong>{{ stats.places }}</strong> places</div>
      <div><strong>{{ stats.years }}</strong> years</div>
      <div><strong>{{ stats.concepts }}</strong> concepts hit</div>
      <div><strong>{{ stats.quantities }}</strong> quantities</div>
      <div v-if="stats.text_yield_avg != null"><strong>{{ (stats.text_yield_avg * 100).toFixed(1) }}%</strong> text yield</div>
    </section>

    <main>
      <div v-if="error" class="err">{{ error }}</div>
      <DocumentsView v-if="view === 'docs'" :documents="documents" :stats="stats" :detail="detail" @open="openDoc"/>
      <MapView v-if="view === 'map'" :places="places" @place="onPlace"/>
      <TimelineView v-if="view === 'time'" :timeline="timeline" @year="onYear" @range="onYearRange"/>
      <ConceptsView v-if="view === 'concepts'" :concept-list="conceptList" @concept="onConcept" @reload="reload"/>
      <MeasuresView v-if="view === 'measures'" :measures="measures" :filters="filters" @unit="onUnit"/>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { get } from './api.js'
import DocumentsView from './views/DocumentsView.vue'
import MapView from './views/MapView.vue'
import TimelineView from './views/TimelineView.vue'
import ConceptsView from './views/ConceptsView.vue'
import MeasuresView from './views/MeasuresView.vue'

const views = [
  { id: 'docs', label: 'Documents' },
  { id: 'map', label: 'Map' },
  { id: 'time', label: 'Timeline' },
  { id: 'concepts', label: 'Concepts' },
  { id: 'measures', label: 'Measurements' }
]
const allowed = new Set(views.map(v => v.id))
const initial = new URLSearchParams(location.search).get('view')
const view = ref(allowed.has(initial) ? initial : 'docs')
const filters = reactive({ q: '', concept: '', place: '', year_min: '', year_max: '', unit: '' })
const stats = ref({})
const documents = ref([])
const places = ref([])
const timeline = ref({ years: [], heatmap: [], decades: [] })
const conceptList = ref([])
const measures = ref([])
const unitOptions = ref([])
const detail = ref(null)
const error = ref('')
const placeOptions = ref([])
const placeNames = computed(() => {
  const names = placeOptions.value.map(p => p.name)
  if (filters.place && !names.includes(filters.place)) names.unshift(filters.place)
  return names
})
const activeFilter = computed(() => {
  const bits = []
  if (filters.place) bits.push('place: ' + filters.place)
  if (filters.concept) bits.push('concept: ' + filters.concept)
  if (filters.year_min !== '' || filters.year_max !== '') {
    bits.push('years: ' + (filters.year_min || '…') + '–' + (filters.year_max || '…'))
  }
  if (filters.unit) bits.push('unit: ' + filters.unit)
  if (filters.q) bits.push('text: ' + filters.q)
  return bits.join(' · ')
})

async function reload() {
  error.value = ''
  try {
    const f = { ...filters }
    stats.value = await get('/api/stats', f)
    documents.value = await get('/api/documents', f)
    places.value = await get('/api/places', f)
    placeOptions.value = await get('/api/places', { ...f, place: '' })
    timeline.value = await get('/api/timeline', f)
    conceptList.value = await get('/api/concepts', f)
    unitOptions.value = await get('/api/measurements', { ...f, unit: '' })
    measures.value = await get('/api/measurements', f)
  } catch (e) {
    error.value = e.message || String(e)
  }
}

function clearFilters() {
  filters.q = filters.concept = filters.place = filters.year_min = filters.year_max = filters.unit = ''
  detail.value = null
  reload()
}

async function openDoc(id) {
  detail.value = await get('/api/documents/' + id)
}

function onPlace(name) {
  filters.place = name
  view.value = 'docs'
  reload()
}
function onYear(year) {
  filters.year_min = year
  filters.year_max = year
  reload()
}
function onYearRange({ min, max }) {
  filters.year_min = min
  filters.year_max = max
  reload()
}
function onConcept(id) {
  filters.concept = id
  reload()
}
function onUnit(unit) {
  filters.unit = unit
  reload()
}

onMounted(reload)
</script>

<style scoped>
.shell { min-height: 100%; display: flex; flex-direction: column; }
.mast {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.8rem 1.4rem; border-bottom: 2px solid var(--gold);
  background: var(--card);
}
.brand { display: flex; gap: 0.7rem; align-items: center; color: var(--sea); }
.mark { width: 2rem; height: 2rem; }
h1 { margin: 0; font-size: 1.4rem; letter-spacing: 0.02em; }
.brand p { margin: 0; font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
nav button {
  background: none; border: none; padding: 0.4rem 0.7rem; cursor: pointer; color: var(--muted); font-weight: 600;
}
nav button.active { color: var(--sea); border-bottom: 2px solid var(--gold); }
.filters {
  display: flex; flex-wrap: wrap; gap: 0.45rem; padding: 0.8rem 1.4rem;
  border-bottom: 1px solid var(--line); background: var(--card);
}
.filters input, .filters select { padding: 0.35rem 0.5rem; border: 1px solid var(--line); border-radius: 4px; background: #fff; }
.go { background: var(--sea); color: #fff; border: none; padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer; }
.chip {
  align-self: center; font-size: 0.8rem; color: var(--sea);
  background: #e8eef0; padding: 0.2rem 0.55rem; border-radius: 99px;
}
.stats {
  display: flex; flex-wrap: wrap; gap: 1.4rem; padding: 0.6rem 1.4rem; font-size: 0.9rem; color: var(--muted);
}
.stats strong { color: var(--sea); }
main { padding: 1rem 1.4rem 2rem; flex: 1; }
.err { color: #9b2335; }
</style>
