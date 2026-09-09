<template>
  <section>
    <h3>Hits in this cut</h3>
    <div ref="barEl" class="chart"></div>
    <template v-if="(cooccur.other || []).length && (cooccur.nodes || []).some(n => n.selected)">
      <h3>Also in these documents</h3>
      <p class="muted">Concepts that co-occur with the current concept filter. Click to OR into the filter.</p>
      <div ref="coEl" class="chart"></div>
    </template>
    <h3 class="co">Co-occurrence</h3>
    <p class="muted co-cap">Together in the same documents. Gold nodes are in the filter.</p>
    <div ref="graphEl" class="graph"></div>
    <ul class="plain">
      <li v-for="c in conceptList" :key="c.id">
        <button class="link" @click="$emit('concept', c.id)">{{ c.label }}</button>
        <span class="muted">{{ c.hits }} hits · {{ c.aliases.join(', ') }}</span>
      </li>
    </ul>
    <form class="editor" @submit.prevent="add">
      <h3>Add a concept</h3>
      <input v-model="id" placeholder="id (sea-ice)" required/>
      <input v-model="label" placeholder="Label" required/>
      <input v-model="aliases" placeholder="aliases, comma separated"/>
      <button class="go" type="submit">Save and rematch</button>
    </form>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { barChart, cooccurGraph, paint } from '../charts.js'
import { post } from '../api.js'

const props = defineProps({
  conceptList: { type: Array, default: () => [] },
  cooccur: { type: Object, default: () => ({ nodes: [], links: [], other: [] }) },
  weight: { type: String, default: 'idf' }
})
const emit = defineEmits(['concept', 'reload'])
const barEl = ref(null)
const coEl = ref(null)
const graphEl = ref(null)
const id = ref('')
const label = ref('')
const aliases = ref('')

function metric() {
  return props.weight === 'raw' ? 'hits' : 'score'
}

function draw() {
  const y = metric()
  paint(() => {
    barChart(barEl.value, props.conceptList.filter(c => c.hits).map(c => ({
      label: c.label, hits: c.hits, score: c.score, documents: c.documents
    })), {
      y,
      onClick: d => {
        const hit = props.conceptList.find(c => c.label === d.label)
        if (hit) emit('concept', hit.id)
      }
    })
    if (coEl.value) {
      barChart(coEl.value, (props.cooccur.other || []).map(c => ({
        label: c.label, hits: c.hits, score: c.score, documents: c.documents, id: c.id
      })), {
        y,
        onClick: d => emit('concept', d.id)
      })
    }
    cooccurGraph(graphEl.value, props.cooccur, {
      metric: props.weight === 'raw' ? 'hits' : 'score',
      onClick: d => emit('concept', d.id)
    })
  })
}

async function add() {
  await post('/api/concepts', {
    id: id.value,
    label: label.value,
    aliases: aliases.value.split(',').map(s => s.trim()).filter(Boolean)
  })
  id.value = label.value = aliases.value = ''
  emit('reload')
}

onMounted(draw)
watch(() => [props.conceptList, props.cooccur, props.weight], draw, { deep: true })
</script>

<style scoped>
.chart { width: 100%; min-height: 8rem; }
.graph { width: 100%; line-height: 0; margin: 0.15rem 0 0.4rem; }
.co { margin: 0.55rem 0 0.1rem; }
.co-cap { margin: 0 0 0.2rem; }
.plain { list-style: none; padding: 0; }
.plain li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.15rem 0.85rem; margin: 0.35rem 0; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
.editor {
  margin-top: 1.2rem; display: flex; flex-wrap: wrap; gap: 0.4rem;
  background: var(--card); padding: 1rem; border: 1px solid var(--line); border-radius: 8px;
}
.editor input { padding: 0.35rem 0.5rem; border: 1px solid var(--line); min-width: 10rem; }
.go { background: var(--sea); color: #fff; border: none; padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer; }
h3 { margin: 1rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
</style>
