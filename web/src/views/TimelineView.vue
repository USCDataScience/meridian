<template>
  <section>
    <p class="muted">
      Extracted dates, not publication year.
      The ribbon is the <em>full</em> span ({{ span }}) — empty years stay visible as light cells.
      Decades with dates is the year-by-year grid. Year × month starts at the newest 50 years;
      load older to walk back toward {{ oldest }}.
    </p>
    <h3>Full span</h3>
    <div ref="ribbonEl" class="chart ribbon"></div>
    <h3>Decades with dates</h3>
    <div ref="decHeatEl" class="chart"></div>
    <h3>Year × month</h3>
    <p class="muted">Newest first · showing {{ visibleYearList.length }} of {{ allYearList.length }} years</p>
    <div ref="heatEl" class="chart"></div>
    <button v-if="visibleYearList.length < allYearList.length" class="more" @click="monthPage += 50">
      Load more ({{ allYearList.length - visibleYearList.length }} left)
    </button>
    <h3>Mentions by decade</h3>
    <div ref="decEl" class="chart"></div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { barChart, decadeHeatmap, heatmap, paint, yearRibbon } from '../charts.js'

const props = defineProps({ timeline: { type: Object, default: () => ({ years: [], heatmap: [], decades: [] }) } })
const emit = defineEmits(['year', 'range'])

const ribbonEl = ref(null)
const decHeatEl = ref(null)
const heatEl = ref(null)
const decEl = ref(null)
const monthPage = ref(50)

const span = computed(() => {
  const ys = (props.timeline.years || []).map(d => d.year)
  if (!ys.length) return '—'
  return Math.min(...ys) + '–' + Math.max(...ys)
})
const oldest = computed(() => {
  const ys = (props.timeline.years || []).map(d => d.year)
  return ys.length ? Math.min(...ys) : '—'
})

function allMonthCells() {
  const years = props.timeline.years || []
  const heat = props.timeline.heatmap || []
  const monthSum = {}
  heat.forEach(d => {
    monthSum[d.year] = (monthSum[d.year] || 0) + d.mentions
  })
  const extra = years.map(y => ({
    year: y.year,
    month: 0,
    mentions: Math.max(0, (y.mentions || 0) - (monthSum[y.year] || 0)),
    documents: y.documents
  })).filter(d => d.mentions > 0)
  return [...heat, ...extra]
}

const allYearList = computed(() => {
  return [...new Set(allMonthCells().map(d => d.year))].sort((a, b) => b - a)
})
const visibleYearList = computed(() => allYearList.value.slice(0, monthPage.value))

function monthCells() {
  const keep = new Set(visibleYearList.value)
  return allMonthCells().filter(d => keep.has(d.year))
}

function draw() {
  paint(() => {
    const years = props.timeline.years || []
    yearRibbon(ribbonEl.value, years, { onClick: d => emit('year', d.year) })
    decadeHeatmap(decHeatEl.value, years, { onClick: d => emit('year', d.year) })
    heatmap(heatEl.value, monthCells(), { onClick: d => emit('year', d.year), newestFirst: true })
    barChart(decEl.value, (props.timeline.decades || []).slice().reverse().map(d => ({
      label: String(d.decade) + 's',
      count: d.mentions,
      decade: d.decade
    })), {
      onClick: d => emit('range', { min: d.decade, max: d.decade + 9 })
    })
  })
}
onMounted(draw)
watch(() => [props.timeline, monthPage.value], draw, { deep: true })
watch(() => props.timeline, () => { monthPage.value = 50 })
</script>

<style scoped>
h3 { margin: 1rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
.chart { width: 100%; min-height: 4rem; }
.ribbon { min-height: 4.2rem; }
.muted { color: var(--muted); }
.muted em { font-style: italic; }
.more {
  margin: 0.6rem 0 1rem; background: var(--sea); color: #fff; border: none;
  padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer;
}
</style>
