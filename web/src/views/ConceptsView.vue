<template>
  <section>
    <div ref="barEl" class="chart"></div>
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
import { barChart, paint } from '../charts.js'
import { post } from '../api.js'

const props = defineProps({ conceptList: { type: Array, default: () => [] } })
const emit = defineEmits(['concept', 'reload'])
const barEl = ref(null)
const id = ref('')
const label = ref('')
const aliases = ref('')

function draw() {
  paint(() => barChart(barEl.value, props.conceptList.filter(c => c.hits).map(c => ({ label: c.label, count: c.hits })), {
    onClick: d => {
      const hit = props.conceptList.find(c => c.label === d.label)
      if (hit) emit('concept', hit.id)
    }
  }))
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
watch(() => props.conceptList, draw, { deep: true })
</script>

<style scoped>
.chart { width: 100%; min-height: 8rem; }
.plain { list-style: none; padding: 0; }
.plain li { margin: 0.35rem 0; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
.editor {
  margin-top: 1.2rem; display: flex; flex-wrap: wrap; gap: 0.4rem;
  background: var(--card); padding: 1rem; border: 1px solid var(--line); border-radius: 8px;
}
.editor input { padding: 0.35rem 0.5rem; border: 1px solid var(--line); min-width: 10rem; }
.go { background: var(--sea); color: #fff; border: none; padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer; }
h3 { margin: 0 0 0.4rem; width: 100%; }
</style>
