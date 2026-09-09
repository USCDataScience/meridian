<template>
  <section>
    <p class="muted">
      Bubbles are places in the <em>current document set</em>, sized by mention count.
      Click a circle to OR that place into the filter. Draw a region to OR a bounding box.
    </p>
    <p v-if="selected.length" class="muted">
      Places {{ selected.join(', ') }}
      · {{ otherCount }} other places in those documents (list below).
    </p>
    <div class="toolbar">
      <button :class="{ on: drawing }" @click="drawing = !drawing">
        {{ drawing ? 'Drawing region — drag on the map' : 'Draw region' }}
      </button>
      <label v-if="!selected.length">Top <input type="range" min="10" max="160" step="5" v-model.number="top"/> {{ top }}</label>
      <span class="muted" v-if="!selected.length">{{ located.length }} located · {{ unresolved.length }} unresolved</span>
      <span class="muted" v-else>showing {{ selected.join(', ') }} on the map</span>
    </div>
    <div ref="mapEl" class="map"></div>
    <h3 v-if="selected.length || bboxes.length">Also in these documents</h3>
    <ul class="plain">
      <li v-for="p in shown" :key="p.name">
        <button class="link" @click="$emit('place', p.name)">{{ p.name }}</button>
        <span class="muted">{{ p.count }} · {{ p.lat != null ? p.lat.toFixed(2)+','+p.lon.toFixed(2) : 'unresolved' }}</span>
      </li>
    </ul>
    <p v-if="listSource.length" class="muted">Showing {{ shown.length }} of {{ listSource.length }}</p>
    <button v-if="shown.length < listSource.length" class="more" @click="loadMore">
      Load more ({{ listSource.length - shown.length }} left)
    </button>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { bubbleMap, paint } from '../charts.js'

const PAGE = 25
const props = defineProps({
  places: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  bboxes: { type: Array, default: () => [] },
  weight: { type: String, default: 'idf' }
})
const emit = defineEmits(['place', 'bbox'])

const mapEl = ref(null)
const top = ref(80)
const shownN = ref(PAGE)
const drawing = ref(false)
const located = computed(() => props.places.filter(p => p.lat != null && p.lon != null))
const unresolved = computed(() => props.places.filter(p => p.lat == null))
const want = computed(() => new Set(props.selected.map(s => s.toLowerCase().trim())))
const selectedPlaces = computed(() =>
  props.places.filter(p => want.value.has((p.name || '').toLowerCase().trim()))
)
const inBbox = computed(() => {
  if (!props.bboxes.length) return []
  return located.value.filter(p => props.bboxes.some(b =>
    p.lat >= b.south && p.lat <= b.north && p.lon >= b.west && p.lon <= b.east
  ))
})
const mapPlaces = computed(() => {
  if (selectedPlaces.value.length) return selectedPlaces.value
  if (inBbox.value.length) return inBbox.value
  return located.value.slice(0, top.value)
})
const listSource = computed(() => {
  if (!props.selected.length && !props.bboxes.length) return props.places
  const skip = want.value
  return props.places.filter(p => !skip.has((p.name || '').toLowerCase().trim()))
})
const shown = computed(() => listSource.value.slice(0, shownN.value))
const otherCount = computed(() => listSource.value.length)

function loadMore() {
  if (shownN.value >= listSource.value.length) return
  shownN.value = Math.min(shownN.value + PAGE, listSource.value.length)
}

function draw() {
  paint(() => bubbleMap(mapEl.value, mapPlaces.value, {
    onClick: p => emit('place', p.name),
    metric: props.weight === 'raw' ? 'count' : 'score',
    brushable: drawing.value,
    onBrush: b => {
      drawing.value = false
      emit('bbox', b)
    }
  }))
}
onMounted(draw)
watch(() => [props.places, props.selected, props.bboxes, props.weight, top.value, drawing.value], draw, { deep: true })
watch(() => [props.places, props.selected], () => { shownN.value = PAGE })
</script>

<style scoped>
.map { width: 100%; min-height: 22rem; background: #dce6ea; border-radius: 8px; overflow: hidden; margin: 0.6rem 0 1rem; }
.toolbar { display: flex; gap: 1.2rem; align-items: center; flex-wrap: wrap; }
.toolbar button {
  background: #fff; border: 1px solid var(--line); padding: 0.3rem 0.7rem; border-radius: 4px; cursor: pointer;
}
.toolbar button.on { background: var(--sea); color: #fff; border-color: var(--sea); }
.plain { list-style: none; padding: 0; columns: 2; }
.plain li { margin: 0.3rem 0; break-inside: avoid; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
h3 { margin: 0.8rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
.more {
  margin: 0.5rem 0 1rem; background: var(--sea); color: #fff; border: none;
  padding: 0.35rem 0.8rem; border-radius: 4px; cursor: pointer;
}
@media (max-width: 800px) { .plain { columns: 1; } }
</style>
