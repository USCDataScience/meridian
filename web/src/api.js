const LIST = {
  concepts: 'concept',
  places: 'place',
  persons: 'person',
  orgs: 'org',
  units: 'unit'
}

export function params(f = {}) {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  for (const [key, qname] of Object.entries(LIST)) {
    for (const v of f[key] || []) {
      if (v !== '' && v != null) p.append(qname, v)
    }
  }
  for (const y of f.years || []) {
    const lo = y.min ?? ''
    const hi = y.max ?? ''
    if (lo === '' && hi === '') continue
    p.append('year', `${lo}-${hi}`)
  }
  for (const b of f.bboxes || []) {
    p.append('bbox', [b.west, b.south, b.east, b.north].join(','))
  }
  const skip = new Set([
    'q', 'concepts', 'places', 'persons', 'orgs', 'units', 'years', 'bboxes',
    'concept', 'place', 'person', 'org'
  ])
  Object.entries(f).forEach(([k, v]) => {
    if (skip.has(k) || v === '' || v == null || Array.isArray(v) || typeof v === 'object') return
    p.append(k, v)
  })
  return p.toString()
}

export function emptyFilters() {
  return { q: '', concepts: [], places: [], persons: [], orgs: [], units: [], years: [], bboxes: [] }
}

function parseYear(s) {
  const raw = (s || '').trim()
  if (!raw) return null
  if (raw.includes('-')) {
    const [a, b] = raw.split('-', 2)
    const min = a === '' ? null : Number(a)
    const max = b === '' ? null : Number(b)
    if (min == null && max == null) return null
    return { min, max }
  }
  const y = Number(raw)
  return Number.isFinite(y) ? { min: y, max: y } : null
}

function parseBbox(s) {
  const p = (s || '').split(',').map(Number)
  if (p.length !== 4 || p.some(n => !Number.isFinite(n))) return null
  return { west: p[0], south: p[1], east: p[2], north: p[3] }
}

export function fromSearch(search) {
  const p = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  const f = emptyFilters()
  f.q = p.get('q') || ''
  f.concepts = p.getAll('concept')
  f.places = p.getAll('place')
  f.persons = p.getAll('person')
  f.orgs = p.getAll('org')
  f.units = p.getAll('unit')
  f.years = p.getAll('year').map(parseYear).filter(Boolean)
  f.bboxes = p.getAll('bbox').map(parseBbox).filter(Boolean)
  const view = p.get('view') || 'docs'
  const weight = p.get('weight') === 'raw' ? 'raw' : 'idf'
  return { filters: f, view, weight }
}

export function toSearch({ filters, view, weight }) {
  const p = new URLSearchParams(params(filters || {}))
  if (view && view !== 'docs') p.set('view', view)
  if (weight && weight !== 'idf') p.set('weight', weight)
  return p.toString()
}

export function exportUrl(filters, fmt) {
  const q = params(filters)
  const extra = 'fmt=' + encodeURIComponent(fmt)
  return q ? `/api/export?${q}&${extra}` : `/api/export?${extra}`
}

export async function get(path, filters = {}) {
  const q = params(filters)
  const r = await fetch(q ? `${path}?${q}` : path)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function post(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
