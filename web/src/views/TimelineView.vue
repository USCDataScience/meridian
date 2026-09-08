<template>
  <section>
    <p class="muted">Year–month heatmap of extracted dates (not just publication year). Click a cell to set the year filter.</p>
    <h3>Year × month</h3>
    <div ref="heatEl" class="chart"></div>
    <h3>Mentions by decade</h3>
    <div ref="decEl" class="chart"></div>
    <h3>Documents by year</h3>
    <div ref="yearEl" class="chart"></div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { barChart, heatmap, paint } from '../charts.js'

const props = defineProps({ timeline: { type: Object, default: () => ({ years: [], heatmap: [], decades: [] }) } })
const emit = defineEmits(['year'])

const heatEl = ref(null)
const decEl = ref(null)
const yearEl = ref(null)

function draw() {
  paint(() => {
    heatmap(heatEl.value, props.timeline.heatmap || [], {
      onClick: d => emit('year', d.year)
    })
    barChart(decEl.value, (props.timeline.decades || []).map(d => ({ label: String(d.decade) + 's', count: d.mentions })), {
      onClick: d => emit('year', parseInt(d.label, 10))
    })
    barChart(yearEl.value, (props.timeline.years || []).map(d => ({ label: String(d.year), count: d.documents })), {
      onClick: d => emit('year', parseInt(d.label, 10))
    })
  })
}
onMounted(draw)
watch(() => props.timeline, draw, { deep: true })
</script>

<style scoped>
h3 { margin: 1rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
.chart { width: 100%; min-height: 6rem; }
.muted { color: var(--muted); }
</style>
