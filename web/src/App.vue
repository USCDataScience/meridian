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
      <button class="go" @click="reload">Apply</button>
      <button @click="clearFilters">Clear</button>
    </section>

    <section class="stats" v-if="stats">
      <div><strong>{{ stats.documents }}</strong> documents</div>
      <div><strong>{{ stats.places }}</strong> places</div>
      <div><strong>{{ stats.years }}</strong> years</div>
      <div><strong>{{ stats.concepts }}</strong> concepts hit</div>
      <div><strong>{{ stats.quantities }}</strong> quantities</div>
    </section>

    <main>
      <div v-if="error" class="err">{{ error }}</div>

      <section v-if="view === 'docs'">
        <table>
          <thead><tr><th>File</th><th>Type</th><th>Year</th></tr></thead>
          <tbody>
            <tr v-for="d in documents" :key="d.id" @click="openDoc(d.id)" class="click">
              <td>{{ d.filename }}</td>
              <td class="muted">{{ d.mime }}</td>
              <td>{{ d.year || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!documents.length" class="muted">No documents. Run <code>meridian index ./demo</code>.</p>
        <article v-if="detail" class="detail">
          <h2>{{ detail.filename }}</h2>
          <p class="muted">{{ detail.path }}</p>
          <p><strong>Places:</strong> {{ detail.places.map(p => p.name).join(', ') || '—' }}</p>
          <p><strong>Years:</strong> {{ detail.years.join(', ') || '—' }}</p>
          <p><strong>Concepts:</strong> {{ detail.concepts.map(c => c.label).join(', ') || '—' }}</p>
          <pre>{{ detail.text }}</pre>
        </article>
      </section>

      <section v-if="view === 'map'">
        <p class="muted">Places with coordinates. Unresolved names stay in the list.</p>
        <div class="bubbles">
          <div v-for="p in located" :key="p.name" class="bubble" :title="p.name + ' ' + p.count"
               :style="bubbleStyle(p)">
            {{ p.name }} <em>{{ p.count }}</em>
          </div>
        </div>
        <ul class="plain">
          <li v-for="p in places" :key="p.name">
            <button class="link" @click="filters.place = p.name; reload()">{{ p.name }}</button>
            <span class="muted">{{ p.count }} · {{ p.lat != null ? p.lat.toFixed(2)+','+p.lon.toFixed(2) : 'unresolved' }}</span>
          </li>
        </ul>
      </section>

      <section v-if="view === 'time'">
        <div class="bars">
          <div v-for="t in timeline" :key="t.year" class="bar-row click" @click="filters.year_min = filters.year_max = t.year; reload()">
            <span>{{ t.year }}</span>
            <div class="bar"><i :style="{ width: (100 * t.count / maxTime) + '%' }"></i></div>
            <span>{{ t.count }}</span>
          </div>
        </div>
      </section>

      <section v-if="view === 'concepts'">
        <ul class="plain">
          <li v-for="c in conceptList" :key="c.id">
            <button class="link" @click="filters.concept = c.id; reload()">{{ c.label }}</button>
            <span class="muted">{{ c.hits }} hits · {{ c.aliases.join(', ') }}</span>
          </li>
        </ul>
        <form class="editor" @submit.prevent="addConcept">
          <h3>Add a concept</h3>
          <input v-model="newConcept.id" placeholder="id (sea-ice)" required/>
          <input v-model="newConcept.label" placeholder="Label" required/>
          <input v-model="newConcept.aliases" placeholder="aliases, comma separated"/>
          <button class="go" type="submit">Save and rematch</button>
        </form>
      </section>

      <section v-if="view === 'measures'">
        <div class="bars">
          <div v-for="m in measures" :key="m.unit" class="bar-row">
            <span>{{ m.unit }}</span>
            <div class="bar"><i :style="{ width: (100 * m.count / maxMeas) + '%' }"></i></div>
            <span>{{ m.count }}</span>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { get, post } from './api.js'

const views = [
  { id: 'docs', label: 'Documents' },
  { id: 'map', label: 'Map' },
  { id: 'time', label: 'Timeline' },
  { id: 'concepts', label: 'Concepts' },
  { id: 'measures', label: 'Measurements' }
]
const view = ref('docs')
const filters = reactive({ q: '', concept: '', place: '', year_min: '', year_max: '' })
const stats = ref(null)
const documents = ref([])
const places = ref([])
const timeline = ref([])
const conceptList = ref([])
const measures = ref([])
const detail = ref(null)
const error = ref('')
const newConcept = reactive({ id: '', label: '', aliases: '' })

const placeNames = computed(() => places.value.map(p => p.name))
const located = computed(() => places.value.filter(p => p.lat != null && p.lon != null))
const maxTime = computed(() => Math.max(1, ...timeline.value.map(t => t.count)))
const maxMeas = computed(() => Math.max(1, ...measures.value.map(m => m.count)))

function bubbleStyle(p) {
  const xs = located.value.map(x => x.lon)
  const ys = located.value.map(x => x.lat)
  const minx = Math.min(...xs), maxx = Math.max(...xs)
  const miny = Math.min(...ys), maxy = Math.max(...ys)
  const dx = (maxx - minx) || 1
  const dy = (maxy - miny) || 1
  const left = ((p.lon - minx) / dx) * 90 + 2
  const top = (1 - (p.lat - miny) / dy) * 70 + 4
  const size = 1.6 + Math.log2(1 + p.count)
  return {
    left: left + '%',
    top: top + '%',
    fontSize: size + 'rem'
  }
}

async function reload() {
  error.value = ''
  try {
    const f = { ...filters }
    stats.value = await get('/api/stats')
    documents.value = await get('/api/documents', f)
    places.value = await get('/api/places', f)
    timeline.value = await get('/api/timeline', f)
    conceptList.value = await get('/api/concepts', f)
    measures.value = await get('/api/measurements', f)
  } catch (e) {
    error.value = e.message || String(e)
  }
}

function clearFilters() {
  filters.q = filters.concept = filters.place = filters.year_min = filters.year_max = ''
  detail.value = null
  reload()
}

async function openDoc(id) {
  detail.value = await get('/api/documents/' + id)
}

async function addConcept() {
  const aliases = newConcept.aliases.split(',').map(s => s.trim()).filter(Boolean)
  await post('/api/concepts', { id: newConcept.id, label: newConcept.label, aliases })
  newConcept.id = newConcept.label = newConcept.aliases = ''
  await reload()
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
.stats {
  display: flex; gap: 1.4rem; padding: 0.6rem 1.4rem; font-size: 0.9rem; color: var(--muted);
}
.stats strong { color: var(--sea); }
main { padding: 1rem 1.4rem 2rem; flex: 1; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
td, th { padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--line); }
.click { cursor: pointer; }
.click:hover { background: #efe8d8; }
.muted { color: var(--muted); }
.err { color: #9b2335; }
.detail { margin-top: 1.2rem; background: var(--card); border: 1px solid var(--line); padding: 1rem; border-radius: 8px; }
.detail pre { white-space: pre-wrap; font-size: 0.85rem; }
.bars { max-width: 40rem; }
.bar-row { display: grid; grid-template-columns: 5rem 1fr 3rem; gap: 0.5rem; align-items: center; margin: 0.25rem 0; }
.bar { height: 0.7rem; background: #e6e0d4; border-radius: 99px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--sea); }
.plain { list-style: none; padding: 0; }
.plain li { margin: 0.35rem 0; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.bubbles { position: relative; height: 16rem; background: #e8eef0; border-radius: 8px; margin-bottom: 1rem; overflow: hidden; }
.bubble { position: absolute; color: var(--sea); font-weight: 700; }
.bubble em { font-style: normal; color: var(--gold); font-size: 0.75em; }
.editor {
  margin-top: 1.2rem; display: flex; flex-wrap: wrap; gap: 0.4rem;
  background: var(--card); padding: 1rem; border: 1px solid var(--line); border-radius: 8px;
}
.editor input { padding: 0.35rem 0.5rem; border: 1px solid var(--line); min-width: 10rem; }
</style>
