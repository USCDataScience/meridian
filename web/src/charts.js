import * as d3 from 'd3'
import { feature } from 'topojson-client'
import world from './world-110m.json'

export const PALETTE = ['#1a4a5c', '#c9a227', '#3d7a8c', '#9b2335', '#6b8f71', '#c47b3b', '#5c6b8a', '#8a6a4a']

function size(el) {
  const w = Math.max(280, (el && el.clientWidth) || 640)
  return { w, h: Math.max(180, Math.round(w * 0.42)) }
}

function clear(el) {
  d3.select(el).selectAll('*').remove()
}

export function paint(fn) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    try { fn() } catch (err) { console.error('chart', err) }
  }))
}

let tip
function ensureTip() {
  if (!tip) {
    tip = d3.select('body').append('div').attr('class', 'meridian-tip')
  }
  return tip
}

export function showTip(html, ev) {
  const node = ensureTip()
  node.html(html).style('display', 'block')
  moveTip(ev)
}

export function moveTip(ev) {
  if (!tip) return
  const pad = 14
  const tw = tip.node().offsetWidth || 160
  const th = tip.node().offsetHeight || 40
  let x = ev.clientX + pad
  let y = ev.clientY + pad
  if (x + tw > window.innerWidth - 8) x = ev.clientX - tw - 8
  if (y + th > window.innerHeight - 8) y = ev.clientY - th - 8
  tip.style('left', x + 'px').style('top', y + 'px')
}

export function hideTip() {
  if (tip) tip.style('display', 'none')
}

function bindTip(sel, htmlFn) {
  sel
    .on('pointerenter', (ev, d) => showTip(htmlFn(d), ev))
    .on('pointermove', (ev) => moveTip(ev))
    .on('pointerleave', hideTip)
}

const interp = d3.interpolateYlGnBu || d3.interpolateBlues || (t => d3.interpolateRgb('#efe8d8', '#1a4a5c')(t))

export function pieChart(el, rows, { label = 'label', value = 'count', onClick } = {}) {
  if (!el) return
  clear(el)
  const data = (rows || []).filter(d => d[value] > 0)
  if (!data.length) return
  const total = d3.sum(data, d => d[value]) || 1
  const { w } = size(el)
  const h = Math.min(280, Math.max(200, w * 0.45))
  const r = Math.min(w, h) / 2 - 8
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const g = svg.append('g').attr('transform', `translate(${w / 2},${h / 2})`)
  const pie = d3.pie().value(d => d[value]).sort(null)
  const arc = d3.arc().innerRadius(r * 0.45).outerRadius(r)
  const color = d3.scaleOrdinal(PALETTE)
  const html = d => {
    const row = d.data || d
    const pct = (100 * row[value] / total).toFixed(1)
    return `<strong>${row[label]}</strong><br>${row[value]} · ${pct}% of ${total}`
  }
  const slices = g.selectAll('path').data(pie(data)).enter().append('path')
    .attr('d', arc)
    .attr('fill', (d, i) => color(i))
    .attr('stroke', '#fffdf8')
    .attr('stroke-width', 1.5)
    .style('cursor', onClick ? 'pointer' : 'default')
    .on('click', (_, d) => onClick && onClick(d.data))
  bindTip(slices, html)
  const legend = svg.append('g').attr('transform', 'translate(8,8)')
  data.slice(0, 8).forEach((d, i) => {
    const row = legend.append('g').attr('transform', `translate(0,${i * 16})`).style('cursor', 'default')
    row.append('rect').attr('width', 10).attr('height', 10).attr('fill', color(i))
    row.append('text').attr('x', 14).attr('y', 9).attr('font-size', 11).attr('fill', '#12202a')
      .text(`${d[label]} (${d[value]})`)
    bindTip(row, () => html({ data: d }))
    if (onClick) row.style('cursor', 'pointer').on('click', () => onClick(d))
  })
}

export function barChart(el, rows, { x = 'label', y = 'count', onClick } = {}) {
  if (!el) return
  clear(el)
  const data = (rows || []).filter(d => d[y] > 0)
  if (!data.length) return
  const total = d3.sum(data, d => d[y]) || 1
  const { w } = size(el)
  const h = Math.min(360, 22 * data.length + 36)
  const m = { t: 8, r: 16, b: 8, l: 120 }
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleLinear().domain([0, d3.max(data, d => d[y])]).range([m.l, w - m.r])
  const Y = d3.scaleBand().domain(data.map(d => d[x])).range([m.t, h - m.b]).padding(0.2)
  const bars = svg.selectAll('rect').data(data).enter().append('rect')
    .attr('x', m.l).attr('y', d => Y(d[x]))
    .attr('width', d => Math.max(1, X(d[y]) - m.l))
    .attr('height', Y.bandwidth())
    .attr('fill', '#1a4a5c')
    .attr('rx', 3)
    .style('cursor', onClick ? 'pointer' : 'default')
    .on('click', (_, d) => onClick && onClick(d))
  bindTip(bars, d => {
    const bits = [`<strong>${d[x]}</strong>`]
    if (d.hits != null && d.score != null && y === 'score') {
      bits.push(`score ${Number(d[y]).toFixed(2)} · ${d.hits} hits`)
    } else {
      bits.push(`${d[y]}`)
    }
    if (d.documents != null) bits.push(`${d.documents} docs`)
    return bits.join('<br>')
  })
  svg.selectAll('n').data(data).enter().append('text')
    .attr('x', m.l - 6).attr('y', d => Y(d[x]) + Y.bandwidth() / 2 + 4)
    .attr('text-anchor', 'end').attr('font-size', 11).attr('fill', '#12202a')
    .text(d => String(d[x]).slice(0, 18))
  svg.selectAll('v').data(data).enter().append('text')
    .attr('x', d => X(d[y]) + 4).attr('y', d => Y(d[x]) + Y.bandwidth() / 2 + 4)
    .attr('font-size', 10).attr('fill', '#6b7280')
    .text(d => (typeof d[y] === 'number' && y === 'score') ? d[y].toFixed(1) : d[y])
}

export function histogram(el, bins, { onClick } = {}) {
  if (!el) return
  clear(el)
  const data = bins || []
  if (!data.length) return
  const { w } = size(el)
  const h = 180
  const m = { t: 12, r: 12, b: 28, l: 32 }
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleBand().domain(data.map((_, i) => i)).range([m.l, w - m.r]).padding(0.08)
  const Y = d3.scaleLinear().domain([0, d3.max(data, d => d.count) || 1]).range([h - m.b, m.t])
  const bars = svg.selectAll('rect').data(data).enter().append('rect')
    .attr('x', (_, i) => X(i)).attr('y', d => Y(d.count))
    .attr('width', X.bandwidth())
    .attr('height', d => (h - m.b) - Y(d.count))
    .attr('fill', '#3d7a8c')
    .style('cursor', onClick ? 'pointer' : 'default')
    .on('click', (_, d) => onClick && onClick(d))
  bindTip(bars, d => `<strong>${d.lo.toFixed(2)} – ${d.hi.toFixed(2)}</strong><br>${d.count} values`)
  svg.append('g').attr('transform', `translate(0,${h - m.b})`)
    .call(d3.axisBottom(X).tickFormat(i => {
      const d = data[i]
      return d ? d.lo.toFixed(0) : ''
    }).tickValues(data.map((_, i) => i).filter(i => i % Math.ceil(data.length / 6) === 0)))
    .selectAll('text').attr('font-size', 10)
}

export function heatmap(el, cells, { onClick, monthZeroLabel = 'yr', newestFirst = true } = {}) {
  if (!el) return
  clear(el)
  const data = cells || []
  if (!data.length) return
  const years = [...new Set(data.map(d => d.year))].sort((a, b) => newestFirst ? b - a : a - b)
  const hasZero = data.some(d => d.month === 0)
  const months = hasZero ? d3.range(0, 13) : d3.range(1, 13)
  const { w } = size(el)
  const m = { t: 22, r: 12, b: 18, l: 44 }
  const cell = Math.max(10, Math.min(20, (w - m.l - m.r) / months.length - 2))
  const h = m.t + m.b + years.length * (cell + 2)
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleBand().domain(months).range([m.l, m.l + months.length * (cell + 2)]).padding(0.08)
  const Y = d3.scaleBand().domain(years).range([m.t, h - m.b]).padding(0.08)
  const max = d3.max(data, d => d.mentions) || 1
  const color = d3.scaleSequential(interp).domain([0, max])
  const lookup = new Map(data.map(d => [`${d.year}-${d.month}`, d]))
  const labels = hasZero
    ? [monthZeroLabel, ...'JFMAMJJASOND']
    : [...'JFMAMJJASOND']
  months.forEach((mo, i) => {
    svg.append('text').attr('x', X(mo) + X.bandwidth() / 2).attr('y', 14)
      .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#6b7280')
      .text(labels[i])
  })
  years.forEach(y => {
    svg.append('text').attr('x', m.l - 6).attr('y', Y(y) + Y.bandwidth() / 2 + 4)
      .attr('text-anchor', 'end').attr('font-size', 10).attr('fill', '#6b7280').text(y)
    months.forEach(mo => {
      const d = lookup.get(`${y}-${mo}`) || { year: y, month: mo, mentions: 0, documents: 0 }
      const rect = svg.append('rect')
        .datum(d)
        .attr('x', X(mo)).attr('y', Y(y))
        .attr('width', X.bandwidth()).attr('height', Y.bandwidth())
        .attr('rx', 2)
        .attr('fill', d.mentions ? color(d.mentions) : '#efe8d8')
        .style('cursor', d.mentions ? 'pointer' : 'default')
        .on('click', () => d.mentions && onClick && onClick(d))
      bindTip(rect, () => {
        const when = mo === 0 ? String(y) + ' (year only)' : `${y}-${String(mo).padStart(2, '0')}`
        return `<strong>${when}</strong><br>${d.mentions} mentions · ${d.documents} docs`
      })
    })
  })
}

export function yearRibbon(el, years, { onClick } = {}) {
  if (!el) return
  clear(el)
  const rows = years || []
  if (!rows.length) return
  const byYear = new Map(rows.map(d => [d.year, d]))
  const minY = d3.min(rows, d => d.year)
  const maxY = d3.max(rows, d => d.year)
  const all = d3.range(minY, maxY + 1).map(year => byYear.get(year) || { year, mentions: 0, documents: 0 })
  const { w } = size(el)
  const h = 64
  const m = { t: 8, r: 8, b: 18, l: 8 }
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleBand().domain(all.map(d => d.year)).range([m.l, w - m.r]).padding(0.05)
  const max = d3.max(all, d => d.mentions) || 1
  const color = d3.scaleSequential(interp).domain([0, max])
  const cells = svg.selectAll('rect').data(all).enter().append('rect')
    .attr('x', d => X(d.year))
    .attr('y', m.t)
    .attr('width', Math.max(1, X.bandwidth()))
    .attr('height', h - m.t - m.b)
    .attr('fill', d => d.mentions ? color(d.mentions) : '#efe8d8')
    .style('cursor', d => d.mentions ? 'pointer' : 'default')
    .on('click', (_, d) => d.mentions && onClick && onClick(d))
  bindTip(cells, d => d.mentions
    ? `<strong>${d.year}</strong><br>${d.mentions} mentions · ${d.documents} docs`
    : `<strong>${d.year}</strong><br>no extracted dates`)
  const ticks = [minY, maxY]
  const mid = rows.filter(d => d.mentions).sort((a, b) => b.mentions - a.mentions)[0]
  if (mid && !ticks.includes(mid.year)) ticks.splice(1, 0, mid.year)
  ticks.forEach(y => {
    svg.append('text')
      .attr('x', X(y) + X.bandwidth() / 2)
      .attr('y', h - 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#6b7280')
      .text(y)
  })
}

export function decadeArea(el, decades, { onClick } = {}) {
  if (!el) return
  clear(el)
  const raw = (decades || []).filter(d => d.decade != null)
  if (!raw.length) return
  const byDec = new Map(raw.map(d => [d.decade, d]))
  const minD = d3.min(raw, d => d.decade)
  const maxD = d3.max(raw, d => d.decade)
  const all = d3.range(minD, maxD + 1, 10).map(decade => (
    byDec.get(decade) || { decade, mentions: 0, documents: 0 }
  ))
  const total = d3.sum(all, d => d.mentions) || 1
  const { w } = size(el)
  const h = 220
  const m = { t: 18, r: 36, b: 32, l: 42 }
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleLinear().domain([minD, maxD]).range([m.l, w - m.r])
  const Y = d3.scaleSymlog()
    .constant(20)
    .domain([0, d3.max(all, d => d.mentions) || 1])
    .range([h - m.b, m.t])
  const area = d3.area()
    .x(d => X(d.decade))
    .y0(Y(0))
    .y1(d => Y(d.mentions))
    .curve(d3.curveMonotoneX)
  const line = d3.line()
    .x(d => X(d.decade))
    .y(d => Y(d.mentions))
    .curve(d3.curveMonotoneX)

  svg.append('path').datum(all).attr('fill', '#1a4a5c').attr('fill-opacity', 0.16).attr('d', area)
  svg.append('path').datum(all).attr('fill', 'none').attr('stroke', '#1a4a5c')
    .attr('stroke-width', 1.8).attr('d', line)

  const gx = svg.append('g').attr('transform', `translate(0,${h - m.b})`)
    .call(d3.axisBottom(X)
      .tickValues(d3.range(Math.ceil(minD / 100) * 100, maxD + 1, 100))
      .tickFormat(d3.format('d'))
      .tickSizeOuter(0))
  gx.selectAll('text').attr('font-size', 10).attr('fill', '#6b7280')
  gx.selectAll('line, path').attr('stroke', '#d9d3c7')

  const yTicks = [0, 100, 1000].filter(v => v <= (d3.max(all, d => d.mentions) || 0))
  const gy = svg.append('g').attr('transform', `translate(${m.l},0)`)
    .call(d3.axisLeft(Y).tickValues(yTicks).tickSize(-(w - m.l - m.r)).tickFormat(d3.format('~s')))
  gy.select('.domain').remove()
  gy.selectAll('text').attr('font-size', 10).attr('fill', '#6b7280')
  gy.selectAll('.tick line').attr('stroke', '#efe8d8')

  const peak = all.slice().sort((a, b) => b.mentions - a.mentions)[0]
  if (peak && peak.mentions) {
    svg.append('text')
      .attr('x', X(peak.decade) + 8)
      .attr('y', Y(peak.mentions) - 6)
      .attr('font-size', 11)
      .attr('fill', '#1a4a5c')
      .text(`${peak.decade}s · ${peak.mentions}`)
  }

  svg.selectAll('dot').data(all.filter(d => d.mentions)).enter().append('circle')
    .attr('cx', d => X(d.decade))
    .attr('cy', d => Y(d.mentions))
    .attr('r', 2.5)
    .attr('fill', '#1a4a5c')
    .style('pointer-events', 'none')

  const rule = svg.append('line')
    .attr('y1', m.t).attr('y2', h - m.b)
    .attr('stroke', '#c9a227').attr('stroke-width', 1)
    .style('display', 'none')
  const focus = svg.append('circle')
    .attr('r', 5).attr('fill', '#c9a227').attr('stroke', '#fffdf8').attr('stroke-width', 1.5)
    .style('display', 'none')

  function nearest(xm) {
    let decade = Math.round(X.invert(xm) / 10) * 10
    decade = Math.max(minD, Math.min(maxD, decade))
    return all.find(d => d.decade === decade) || all[0]
  }

  function tipHtml(d) {
    const pct = (100 * d.mentions / total).toFixed(1)
    if (!d.mentions) return `<strong>${d.decade}s</strong><br>no extracted dates`
    return `<strong>${d.decade}s</strong><br>${d.mentions} mentions · ${d.documents} docs · ${pct}%`
  }

  svg.append('rect')
    .attr('x', m.l).attr('y', m.t)
    .attr('width', Math.max(0, w - m.l - m.r))
    .attr('height', Math.max(0, h - m.t - m.b))
    .attr('fill', 'transparent')
    .style('cursor', onClick ? 'pointer' : 'crosshair')
    .on('pointermove', ev => {
      const [xm] = d3.pointer(ev, svg.node())
      const d = nearest(xm)
      rule.attr('x1', X(d.decade)).attr('x2', X(d.decade)).style('display', null)
      focus.attr('cx', X(d.decade)).attr('cy', Y(d.mentions))
        .style('display', d.mentions ? null : 'none')
      showTip(tipHtml(d), ev)
    })
    .on('pointerleave', () => {
      hideTip()
      rule.style('display', 'none')
      focus.style('display', 'none')
    })
    .on('click', ev => {
      const [xm] = d3.pointer(ev, svg.node())
      const d = nearest(xm)
      if (d.mentions && onClick) onClick(d)
    })
}

export function decadeHeatmap(el, years, { onClick } = {}) {
  if (!el) return
  clear(el)
  const rows = years || []
  if (!rows.length) return
  const byYear = new Map(rows.map(d => [d.year, d]))
  const decades = [...new Set(rows.map(d => Math.floor(d.year / 10) * 10))].sort((a, b) => b - a)
  const { w } = size(el)
  const m = { t: 18, r: 12, b: 8, l: 44 }
  const cell = Math.max(12, Math.min(22, (w - m.l - m.r) / 10 - 2))
  const h = m.t + m.b + decades.length * (cell + 2)
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleBand().domain(d3.range(0, 10)).range([m.l, m.l + 10 * (cell + 2)]).padding(0.08)
  const Y = d3.scaleBand().domain(decades).range([m.t, h - m.b]).padding(0.08)
  const max = d3.max(rows, d => d.mentions) || 1
  const color = d3.scaleSequential(interp).domain([0, max])
  d3.range(0, 10).forEach(i => {
    svg.append('text').attr('x', X(i) + X.bandwidth() / 2).attr('y', 12)
      .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#6b7280').text(i)
  })
  decades.forEach(dec => {
    svg.append('text').attr('x', m.l - 6).attr('y', Y(dec) + Y.bandwidth() / 2 + 4)
      .attr('text-anchor', 'end').attr('font-size', 10).attr('fill', '#6b7280').text(dec + 's')
    d3.range(0, 10).forEach(i => {
      const year = dec + i
      const d = byYear.get(year) || { year, mentions: 0, documents: 0 }
      const rect = svg.append('rect').datum(d)
        .attr('x', X(i)).attr('y', Y(dec))
        .attr('width', X.bandwidth()).attr('height', Y.bandwidth())
        .attr('rx', 2)
        .attr('fill', d.mentions ? color(d.mentions) : '#efe8d8')
        .style('cursor', d.mentions ? 'pointer' : 'default')
        .on('click', () => d.mentions && onClick && onClick(d))
      bindTip(rect, () => d.mentions
        ? `<strong>${year}</strong><br>${d.mentions} mentions · ${d.documents} docs`
        : `<strong>${year}</strong><br>no extracted dates`)
    })
  })
}

export function bubbleMap(el, places, { onClick, onBrush, brushable = false, metric = 'score' } = {}) {
  if (!el) return
  clear(el)
  const located = (places || []).filter(p => p.lat != null && p.lon != null)
  const { w } = size(el)
  const h = Math.max(320, Math.round(w * 0.48))
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const countries = feature(world, world.objects.countries)
  const clipped = {
    type: 'FeatureCollection',
    features: (countries.features || []).filter(f => {
      try {
        const c = d3.geoCentroid(f)
        return c && c[1] > -58
      } catch {
        return false
      }
    })
  }
  const projection = d3.geoMercator().fitExtent([[8, 16], [w - 8, h - 8]], clipped)
  const path = d3.geoPath(projection)
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#dce6ea')
  svg.append('path').datum(clipped).attr('d', path).attr('fill', '#c5d0d4')
    .attr('stroke', '#9aafb6').attr('stroke-width', 0.4)
    .style('pointer-events', 'none')
  if (located.length) {
    const pts = located.map(d => {
      const xy = projection([d.lon, d.lat])
      return xy && Number.isFinite(xy[0]) ? { ...d, x: xy[0], y: xy[1] } : null
    }).filter(Boolean).sort((a, b) => (b.score || b.count) - (a.score || a.count))
    const val = d => (metric === 'score' && d.score != null ? d.score : d.count) || 0
    const max = d3.max(pts, val) || 1
    const r = d3.scaleSqrt().domain([0, max]).range([5, 28])
    const g = svg.append('g')
    const hits = g.selectAll('hit').data(pts).enter().append('circle')
      .attr('cx', d => d.x).attr('cy', d => d.y)
      .attr('r', d => Math.max(12, r(val(d)) + 6))
      .attr('fill', 'transparent')
      .style('cursor', brushable ? 'crosshair' : 'pointer')
      .style('pointer-events', brushable ? 'none' : 'all')
      .on('click', (ev, d) => {
        ev.stopPropagation()
        onClick && onClick(d)
      })
    bindTip(hits, d => {
      const bits = [`<strong>${d.name}</strong>`, `${d.count} mentions`]
      if (d.documents != null) bits.push(`${d.documents} docs`)
      if (d.score != null) bits.push(`score ${d.score.toFixed(2)}`)
      bits.push(`${d.lat.toFixed(2)}, ${d.lon.toFixed(2)}`, `<em>click to filter</em>`)
      return bits.join('<br>')
    })
    g.selectAll('dot').data(pts).enter().append('circle')
      .attr('cx', d => d.x).attr('cy', d => d.y)
      .attr('r', d => r(val(d)))
      .attr('fill', '#1a4a5c')
      .attr('fill-opacity', 0.45)
      .attr('stroke', '#c9a227')
      .attr('stroke-width', 1)
      .style('pointer-events', 'none')
  }
  if (brushable && onBrush) {
    const brush = d3.brush()
      .extent([[0, 0], [w, h]])
      .on('end', ev => {
        if (!ev.selection) return
        const [[x0, y0], [x1, y1]] = ev.selection
        const a = projection.invert([x0, y1])
        const b = projection.invert([x1, y0])
        if (!a || !b || !Number.isFinite(a[0]) || !Number.isFinite(b[0])) return
        onBrush({
          west: Math.min(a[0], b[0]),
          south: Math.min(a[1], b[1]),
          east: Math.max(a[0], b[0]),
          north: Math.max(a[1], b[1])
        })
      })
    svg.append('g').attr('class', 'brush').call(brush)
  }
}

export function cooccurGraph(el, graph, { onClick, metric = 'score' } = {}) {
  if (!el) return
  clear(el)
  const nodes = (graph?.nodes || []).map(d => ({ ...d }))
  const links = (graph?.links || []).map(d => ({ ...d }))
  if (!nodes.length) return
  const maxW = Math.max(280, (el && el.clientWidth) || 640)
  const val = d => (metric === 'score' && d.score != null ? d.score : d.hits) || 0
  const maxH = d3.max(nodes, val) || 1
  const r = d3.scaleSqrt().domain([0, maxH]).range([14, 36])
  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(90).strength(0.4))
    .force('charge', d3.forceManyBody().strength(-280))
    .force('center', d3.forceCenter(0, 0))
    .force('collide', d3.forceCollide().radius(d => r(val(d)) + 16))
    .stop()
  for (let i = 0; i < 180; i++) sim.tick()
  const labelGap = 16
  const x0 = d3.min(nodes, d => d.x - r(val(d)))
  const x1 = d3.max(nodes, d => d.x + r(val(d)))
  const y0 = d3.min(nodes, d => d.y - r(val(d)))
  const y1 = d3.max(nodes, d => d.y + r(val(d)) + labelGap)
  const bw = Math.max(1, x1 - x0)
  const bh = Math.max(1, y1 - y0)
  const pad = 12
  const targetH = 420
  const scale = Math.min((maxW - 2 * pad) / bw, (targetH - 2 * pad) / bh)
  const w = Math.round(bw * scale + 2 * pad)
  const h = Math.round(bh * scale + 2 * pad)
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const g = svg.append('g').attr(
    'transform',
    `translate(${pad - x0 * scale},${pad - y0 * scale}) scale(${scale})`
  )
  const link = g.selectAll('line').data(links).enter().append('line')
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    .attr('stroke', '#9aafb6')
    .attr('stroke-width', d => Math.max(1.2, Math.min(6, d.documents / 3)) / scale)
  bindTip(link, d => `${d.source.label} · ${d.target.label}<br>${d.documents} documents together`)
  const node = g.selectAll('node').data(nodes).enter().append('g')
    .style('cursor', 'pointer')
    .on('click', (_, d) => onClick && onClick(d))
  node.append('circle')
    .attr('cx', d => d.x).attr('cy', d => d.y)
    .attr('r', d => r(val(d)))
    .attr('fill', d => d.selected ? '#c9a227' : '#1a4a5c')
    .attr('fill-opacity', 0.85)
    .attr('stroke', '#fffdf8')
    .attr('stroke-width', 1.5 / scale)
  node.append('text')
    .attr('x', d => d.x).attr('y', d => d.y + r(val(d)) + 13)
    .attr('text-anchor', 'middle')
    .attr('font-size', 13 / scale)
    .attr('fill', '#12202a')
    .text(d => d.label)
  bindTip(node, d => {
    const bits = [`<strong>${d.label}</strong>`, `${d.hits} hits · ${d.documents} docs`]
    if (d.score != null) bits.push(`score ${d.score.toFixed(2)}`)
    bits.push(`<em>click to add filter</em>`)
    return bits.join('<br>')
  })
}
