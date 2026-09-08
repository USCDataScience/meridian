const params = (f) => {
  const p = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) p.set(k, v)
  })
  return p.toString()
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
