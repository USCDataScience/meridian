<template>
  <section>
    <p class="muted">
      People and organizations from spaCy NER. They are <em>not</em> geocoded.
      Click a name to OR it into the filter.
    </p>
    <div class="tabs">
      <button :class="{ on: kind === 'PERSON' }" @click="kind = 'PERSON'">People</button>
      <button :class="{ on: kind === 'ORG' }" @click="kind = 'ORG'">Organizations</button>
    </div>
    <div ref="barEl" class="chart"></div>
    <ul class="plain">
      <li v-for="e in shown" :key="e.label + e.name">
        <button class="link" @click="pick(e)">{{ e.name }}</button>
        <span class="muted">{{ e.count }} mentions · {{ e.documents }} docs<span v-if="(e.names || []).length > 1"> · also {{ e.names.filter(n => n !== e.name).slice(0, 3).join(', ') }}</span></span>
      </li>
    </ul>
    <p v-if="rows.length" class="muted">Showing {{ shown.length }} of {{ rows.length }}</p>
    <button v-if="shown.length < rows.length" class="more" @click="shownN += 25">
      Load more ({{ rows.length - shown.length }} left)
    </button>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { barChart, paint } from '../charts.js'

const props = defineProps({
  entities: { type: Array, default: () => [] },
  weight: { type: String, default: 'idf' }
})
const emit = defineEmits(['person', 'org'])
const kind = ref('PERSON')
const barEl = ref(null)
const shownN = ref(25)
const rows = computed(() => props.entities.filter(e => e.label === kind.value))
const shown = computed(() => rows.value.slice(0, shownN.value))

function pick(e) {
  if (e.label === 'ORG') emit('org', e.name)
  else emit('person', e.name)
}

function draw() {
  const y = props.weight === 'raw' ? 'count' : 'score'
  paint(() => barChart(barEl.value, rows.value.slice(0, 20).map(e => ({
    label: e.name, count: e.count, hits: e.count, score: e.score, documents: e.documents
  })), {
    y,
    onClick: d => {
      const hit = rows.value.find(e => e.name === d.label)
      if (hit) pick(hit)
    }
  }))
}

onMounted(draw)
watch(() => [props.entities, kind.value, props.weight], () => { shownN.value = 25; draw() }, { deep: true })
</script>

<style scoped>
.tabs { display: flex; gap: 0.4rem; margin: 0.4rem 0 0.8rem; }
.tabs button {
  background: #fff; border: 1px solid var(--line); padding: 0.3rem 0.7rem; border-radius: 4px; cursor: pointer;
}
.tabs button.on { background: var(--sea); color: #fff; border-color: var(--sea); }
.chart { width: 100%; min-height: 8rem; }
.plain { list-style: none; padding: 0; columns: 2; }
.plain li { margin: 0.3rem 0; break-inside: avoid; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
.more {
  margin: 0.5rem 0 1rem; background: var(--sea); color: #fff; border: none;
  padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer;
}
@media (max-width: 800px) { .plain { columns: 1; } }
</style>
