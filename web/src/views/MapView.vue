<template>
  <section>
    <p class="muted">Geocoded mentions as D3 density bubbles. Radius is mention count. Click a circle to filter on that place.</p>
    <div class="toolbar">
      <label>Top <input type="range" min="10" max="160" step="5" v-model.number="top"/> {{ top }}</label>
      <span class="muted">{{ located.length }} located · {{ unresolved.length }} unresolved</span>
    </div>
    <div ref="mapEl" class="map"></div>
    <ul class="plain">
      <li v-for="p in shown" :key="p.name">
        <button class="link" @click="$emit('place', p.name)">{{ p.name }}</button>
        <span class="muted">{{ p.count }} · {{ p.lat != null ? p.lat.toFixed(2) + ',' + p.lon.toFixed(2) : 'unresolved' }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { bubbleMap, paint } from '../charts.js'

const props = defineProps({ places: { type: Array, default: () => [] } })
const emit = defineEmits(['place'])

const mapEl = ref(null)
const top = ref(80)
const located = computed(() => props.places.filter(p => p.lat != null && p.lon != null))
const unresolved = computed(() => props.places.filter(p => p.lat == null))
const shown = computed(() => props.places.slice(0, top.value))

function draw() {
  paint(() => bubbleMap(mapEl.value, located.value.slice(0, top.value), {
    onClick: p => emit('place', p.name)
  }))
}
onMounted(draw)
watch(() => [props.places, top.value], draw, { deep: true })
</script>

<style scoped>
.map { width: 100%; min-height: 22rem; background: #dce6ea; border-radius: 8px; overflow: hidden; margin: 0.6rem 0 1rem; }
.toolbar { display: flex; gap: 1.2rem; align-items: center; }
.plain { list-style: none; padding: 0; columns: 2; }
.plain li { margin: 0.3rem 0; break-inside: avoid; }
.link { background: none; border: none; color: var(--sea); cursor: pointer; font-weight: 600; padding: 0; }
.muted { color: var(--muted); }
@media (max-width: 800px) { .plain { columns: 1; } }
</style>
