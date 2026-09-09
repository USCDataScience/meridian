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
      <select v-model="pickConcept" @change="addConcept(pickConcept)">
        <option value="">Add concept</option>
        <option v-for="c in conceptList" :key="c.id" :value="c.id">{{ c.label }}</option>
      </select>
      <select v-model="pickPlace" @change="addPlace(pickPlace)">
        <option value="">Add place</option>
        <option v-for="p in placeNames" :key="p" :value="p">{{ p }}</option>
      </select>
      <input v-model="yearLo" type="number" placeholder="From year"/>
      <input v-model="yearHi" type="number" placeholder="To year"/>
      <button @click="addYears">Add years</button>
      <select v-model="pickUnit" @change="addUnit(pickUnit)">
        <option value="">Add unit</option>
        <option v-for="m in unitOptions" :key="m.unit" :value="m.unit">{{ m.unit }}</option>
      </select>
      <button class="go" @click="reload">Apply</button>
      <button @click="clearFilters">Clear</button>
      <button :class="{ on: weight === 'idf' }" @click="setWeight('idf')">Distinctive</button>
      <button :class="{ on: weight === 'raw' }" @click="setWeight('raw')">Raw counts</button>
      <button @click="download('json')">Export JSON</button>
      <button @click="download('csv')">Export CSV</button>
    </section>
    <section class="chips" v-if="chips.length">
      <span class="hint">AND across axes · OR within an axis</span>
      <button v-for="c in chips" :key="c.key" class="chip" @click="removeChip(c)">
        {{ c.label }} <span class="x">×</span>
      </button>
    </section>

    <section class="stats" v-if="stats">
      <div><strong>{{ stats.documents }}</strong> documents</div>
      <div><strong>{{ stats.places }}</strong> places</div>
      <div><strong>{{ stats.people || 0 }}</strong> people</div>
      <div><strong>{{ stats.orgs || 0 }}</strong> orgs</div>
      <div><strong>{{ stats.years }}</strong> years</div>
      <div><strong>{{ stats.concepts }}</strong> concepts hit</div>
      <div><strong>{{ stats.quantities }}</strong> quantities</div>
      <div v-if="stats.text_yield_avg != null"><strong>{{ (stats.text_yield_avg * 100).toFixed(1) }}%</strong> text yield</div>
    </section>

    <main>
      <div v-if="error" class="err">{{ error }}</div>
      <DocumentsView v-if="view === 'docs'" :documents="documents" :stats="stats" :detail="detail" @open="openDoc"/>
      <MapView v-if="view === 'map'" :places="places" :selected="filters.places" :bboxes="filters.bboxes"
               :weight="weight" @place="addPlace" @bbox="addBbox"/>
      <TimelineView v-if="view === 'time'" :timeline="timeline" @year="onYear" @range="onYearRange"/>
      <ConceptsView v-if="view === 'concepts'" :concept-list="conceptList" :cooccur="cooccur"
                    :weight="weight" @concept="addConcept" @reload="reload"/>
      <EntitiesView v-if="view === 'entities'" :entities="entities" :weight="weight"
                    @person="addPerson" @org="addOrg"/>
      <MeasuresView v-if="view === 'measures'" :measures="measures" :filters="filters" @unit="addUnit"/>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { emptyFilters, exportUrl, fromSearch, get, toSearch } from './api.js'
import DocumentsView from './views/DocumentsView.vue'
import MapView from './views/MapView.vue'
import TimelineView from './views/TimelineView.vue'
import ConceptsView from './views/ConceptsView.vue'
import EntitiesView from './views/EntitiesView.vue'
import MeasuresView from './views/MeasuresView.vue'

const views = [
  { id: 'docs', label: 'Documents' },
  { id: 'map', label: 'Map' },
  { id: 'time', label: 'Timeline' },
  { id: 'concepts', label: 'Concepts' },
  { id: 'entities', label: 'Entities' },
  { id: 'measures', label: 'Measurements' }
]
const allowed = new Set(views.map(v => v.id))
const boot = fromSearch(location.search)
const view = ref(allowed.has(boot.view) ? boot.view : 'docs')
const weight = ref(boot.weight)
const filters = reactive({ ...emptyFilters(), ...boot.filters })
const pickConcept = ref('')
const pickPlace = ref('')
const pickUnit = ref('')
const yearLo = ref('')
const yearHi = ref('')
const stats = ref({})
const documents = ref([])
const places = ref([])
const timeline = ref({ years: [], heatmap: [], decades: [] })
const conceptList = ref([])
const cooccur = ref({ nodes: [], links: [], other: [] })
const entities = ref([])
const measures = ref([])
const unitOptions = ref([])
const detail = ref(null)
const error = ref('')
const placeOptions = ref([])
const placeNames = computed(() => {
  const names = placeOptions.value.map(p => p.name)
  filters.places.forEach(p => { if (!names.includes(p)) names.unshift(p) })
  return names
})

const chips = computed(() => {
  const out = []
  if (filters.q) out.push({ key: 'q', label: 'text: ' + filters.q })
  filters.concepts.forEach((id, i) => {
    const lab = conceptList.value.find(c => c.id === id)?.label || id
    out.push({ key: 'concepts:' + i, kind: 'concepts', i, label: 'concept: ' + lab })
  })
  filters.places.forEach((p, i) => out.push({ key: 'places:' + i, kind: 'places', i, label: 'place: ' + p }))
  filters.persons.forEach((p, i) => out.push({ key: 'persons:' + i, kind: 'persons', i, label: 'person: ' + p }))
  filters.orgs.forEach((p, i) => out.push({ key: 'orgs:' + i, kind: 'orgs', i, label: 'org: ' + p }))
  filters.units.forEach((u, i) => out.push({ key: 'units:' + i, kind: 'units', i, label: 'unit: ' + u }))
  filters.years.forEach((y, i) => out.push({
    key: 'years:' + i, kind: 'years', i,
    label: 'years: ' + (y.min ?? '…') + '–' + (y.max ?? '…')
  }))
  filters.bboxes.forEach((b, i) => out.push({
    key: 'bboxes:' + i, kind: 'bboxes', i,
    label: 'region: ' + b.west.toFixed(1) + ',' + b.south.toFixed(1) + ' → ' + b.east.toFixed(1) + ',' + b.north.toFixed(1)
  }))
  return out
})

function without(keys) {
  const o = { ...filters }
  keys.forEach(k => { o[k] = [] })
  return o
}

function writeUrl() {
  const q = toSearch({ filters, view: view.value, weight: weight.value })
  const next = q ? `${location.pathname}?${q}` : location.pathname
  const cur = location.pathname + location.search
  if (next !== cur) history.replaceState({ view: view.value }, '', next)
}

function applySearch(search) {
  const parsed = fromSearch(search)
  Object.assign(filters, emptyFilters(), parsed.filters)
  if (allowed.has(parsed.view)) view.value = parsed.view
  weight.value = parsed.weight
}

async function reload() {
  writeUrl()
  error.value = ''
  try {
    const f = { ...filters }
    stats.value = await get('/api/stats', f)
    documents.value = await get('/api/documents', f)
    places.value = await get('/api/places', f)
    placeOptions.value = await get('/api/places', without(['places', 'bboxes']))
    timeline.value = await get('/api/timeline', f)
    conceptList.value = await get('/api/concepts', f)
    cooccur.value = await get('/api/concepts/cooccur', f)
    const [people, orgs] = await Promise.all([
      get('/api/entities', { ...f, label: 'PERSON' }),
      get('/api/entities', { ...f, label: 'ORG' })
    ])
    entities.value = [...people, ...orgs]
    unitOptions.value = await get('/api/measurements', without(['units']))
    measures.value = await get('/api/measurements', f)
  } catch (e) {
    error.value = e.message || String(e)
  }
}

function pushUnique(arr, val) {
  if (val === '' || val == null) return false
  if (arr.includes(val)) return false
  arr.push(val)
  return true
}

function addConcept(id) {
  pickConcept.value = ''
  if (pushUnique(filters.concepts, id)) reload()
}
function addPlace(name) {
  pickPlace.value = ''
  if (pushUnique(filters.places, name)) reload()
}
function addPerson(name) {
  if (pushUnique(filters.persons, name)) reload()
}
function addOrg(name) {
  if (pushUnique(filters.orgs, name)) reload()
}
function addUnit(unit) {
  pickUnit.value = ''
  if (unit === '') return
  if (pushUnique(filters.units, unit)) reload()
}
function addYears() {
  const min = yearLo.value === '' ? null : Number(yearLo.value)
  const max = yearHi.value === '' ? null : Number(yearHi.value)
  if (min == null && max == null) return
  const key = `${min}-${max}`
  if (filters.years.some(y => `${y.min}-${y.max}` === key)) return
  filters.years.push({ min, max })
  reload()
}
function addBbox(b) {
  filters.bboxes.push(b)
  reload()
}
function onYear(year) {
  const key = `${year}-${year}`
  if (filters.years.some(y => `${y.min}-${y.max}` === key)) return
  filters.years.push({ min: year, max: year })
  reload()
}
function onYearRange({ min, max }) {
  const key = `${min}-${max}`
  if (filters.years.some(y => `${y.min}-${y.max}` === key)) return
  filters.years.push({ min, max })
  reload()
}

function removeChip(c) {
  if (c.key === 'q') filters.q = ''
  else if (c.kind) filters[c.kind].splice(c.i, 1)
  reload()
}

function clearFilters() {
  Object.assign(filters, emptyFilters())
  yearLo.value = yearHi.value = ''
  pickConcept.value = pickPlace.value = pickUnit.value = ''
  detail.value = null
  reload()
}

function setWeight(w) {
  if (weight.value === w) return
  weight.value = w
  writeUrl()
}

function download(fmt) {
  window.location.href = exportUrl(filters, fmt)
}

async function openDoc(id) {
  detail.value = await get('/api/documents/' + id)
}

watch(view, writeUrl)
onMounted(() => {
  window.addEventListener('popstate', () => {
    applySearch(location.search)
    reload()
  })
  reload()
})
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
  display: flex; flex-wrap: wrap; gap: 0.45rem; padding: 0.8rem 1.4rem 0.4rem;
  background: var(--card);
}
.filters input, .filters select, .filters button { padding: 0.35rem 0.5rem; border: 1px solid var(--line); border-radius: 4px; background: #fff; cursor: pointer; }
.filters button.go { background: var(--sea); color: #fff; border-color: var(--sea); }
.filters button.on { background: var(--sea); color: #fff; border-color: var(--sea); }
.chips {
  display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
  padding: 0.2rem 1.4rem 0.7rem; border-bottom: 1px solid var(--line); background: var(--card);
}
.hint { font-size: 0.72rem; color: var(--muted); margin-right: 0.4rem; }
.chip {
  font-size: 0.8rem; color: var(--sea); background: #e8eef0; border: none;
  padding: 0.2rem 0.55rem; border-radius: 99px; cursor: pointer;
}
.chip .x { color: var(--muted); margin-left: 0.15rem; }
.stats {
  display: flex; flex-wrap: wrap; gap: 1.4rem; padding: 0.6rem 1.4rem; font-size: 0.9rem; color: var(--muted);
}
.stats strong { color: var(--sea); }
main { padding: 1rem 1.4rem 2rem; flex: 1; }
.err { color: #9b2335; }
</style>
