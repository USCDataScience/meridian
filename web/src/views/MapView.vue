<template>
  <section>
    <p class="muted">
      Bubbles are places in the <em>current document set</em>, sized by mention count.
      Click a circle to keep those documents and show only that place on the map.
    </p>
    <p v-if="selected" class="muted">
      Filtered to <strong>{{ selected }}</strong>
      · {{ documentsHint }}
      · {{ otherCount }} other places in those documents (list below).
    </p>
    <div class="toolbar">
      <label v-if="!selected">Top <input type="range" min="10" max="160" step="5" v-model.number="top"/> {{ top }}</label>
      <span class="muted" v-if="!selected">{{ located.length }} located · {{ unresolved.length }} unresolved</span>
      <span class="muted" v-else>showing {{ selected }} on the map</span>
    </div>
    <div ref="mapEl" class="map"></div>
    <h3 v-if="selected">Also in these documents</h3>
    <ul class="plain">
      <li v-for="p in shown" :key="p.name">
        <button class="link" @click="$emit('place', p.name)">{{ p.name }}</button>
        <span class="muted">{{ p.count }} · {{ p.lat != null ? p.lat.toFixed(2)+','+p.lon.toFixed(2) : 'unresolved' }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { bubbleMap, paint } from '../charts.js'

const props = defineProps({
  places: { type: Array, default: () => [] },
  selected: { type: String, default: '' }
})
const emit = defineEmits(['place'])

const mapEl = ref(null)
const top = ref(80)
const located = computed(() => props.places.filter(p => p.lat != null && p.lon != null))
const unresolved = computed(() => props.places.filter(p => p.lat == null))
const selectedPlace = computed(() => {
  if (!props.selected) return null
  const want = props.selected.toLowerCase().trim()
  return props.places.find(p => (p.name || '').toLowerCase().trim() === want) || null
})
const mapPlaces = computed(() => {
  if (selectedPlace.value) return [selectedPlace.value]
  return located.value.slice(0, top.value)
})
const shown = computed(() => {
  if (!props.selected) return props.places.slice(0, top.value)
  return props.places.filter(p => p.name !== selectedPlace.value?.name).slice(0, top.value)
})
const otherCount = computed(() => Math.max(0, props.places.length - 1))
const documentsHint = computed(() => {
  const p = selectedPlace.value
  return p ? (p.count + ' mentions') : ''
})

function draw() {
  paint(() => bubbleMap(mapEl.value, mapPlaces.value, {
    onClick: p => emit('place', p.name)
  }))
}
onMounted(draw)
watch(() => [props.places, props.selected, top.value], draw, { deep: true })
</script>

<style scoped>
.map { width: 100%; min-height: 22rem; background: #dce6ea; border-radius: 8px; overflow: hidden; margin: 0.6rem 0 1rem; }
.toolbar { display: flex; gap: 1.2rem; align-items: center; }
.plain { list-style: none; padding: 0; columns: 2; }
.plain li { margin: 0.3rem 0; break-inside: avoid; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
h3 { margin: 0.8rem 0 0.3rem; font-size: 0.95rem; color: var(--sea); }
@media (max-width: 800px) { .plain { columns: 1; } }
</style>
