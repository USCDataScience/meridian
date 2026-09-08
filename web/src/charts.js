import * as d3 from 'd3'
import { feature } from 'topojson-client'
import world from './world-110m.json'

export const PALETTE = ['#1a4a5c', '#c9a227', '#3d7a8c', '#9b2335', '#6b8f71', '#c47b3b', '#5c6b8a', '#8a6a4a']

function size(el) {
  const w = Math.max(280, el.clientWidth || 640)
  return { w, h: Math.max(180, Math.round(w * 0.42)) }
}

function clear(el) {
  d3.select(el).selectAll('*').remove()
}

export function pieChart(el, rows, { label = 'label', value = 'count' } = {}) {
  if (!el) return
  clear(el)
  const data = (rows || []).filter(d => d[value] > 0)
  if (!data.length) return
  const { w } = size(el)
  const h = Math.min(280, Math.max(200, w * 0.45))
  const r = Math.min(w, h) / 2 - 8
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const g = svg.append('g').attr('transform', `translate(${w / 2},${h / 2})`)
  const pie = d3.pie().value(d => d[value]).sort(null)
  const arc = d3.arc().innerRadius(r * 0.45).outerRadius(r)
  const color = d3.scaleOrdinal(PALETTE)
  g.selectAll('path').data(pie(data)).enter().append('path')
    .attr('d', arc)
    .attr('fill', (d, i) => color(i))
    .attr('stroke', '#fffdf8')
    .attr('stroke-width', 1.5)
    .append('title')
    .text(d => `${d.data[label]}: ${d.data[value]}`)
  const legend = svg.append('g').attr('transform', `translate(8,8)`)
  data.slice(0, 8).forEach((d, i) => {
    const row = legend.append('g').attr('transform', `translate(0,${i * 16})`)
    row.append('rect').attr('width', 10).attr('height', 10).attr('fill', color(i))
    row.append('text').attr('x', 14).attr('y', 9).attr('font-size', 11).attr('fill', '#12202a')
      .text(`${d[label]} (${d[value]})`)
  })
}

export function barChart(el, rows, { x = 'label', y = 'count', onClick } = {}) {
  if (!el) return
  clear(el)
  const data = (rows || []).filter(d => d[y] > 0)
  if (!data.length) return
  const { w } = size(el)
  const h = Math.min(320, 24 * data.length + 40)
  const m = { t: 8, r: 16, b: 8, l: 120 }
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleLinear().domain([0, d3.max(data, d => d[y])]).range([m.l, w - m.r])
  const Y = d3.scaleBand().domain(data.map(d => d[x])).range([m.t, h - m.b]).padding(0.2)
  svg.selectAll('rect').data(data).enter().append('rect')
    .attr('x', m.l).attr('y', d => Y(d[x]))
    .attr('width', d => Math.max(1, X(d[y]) - m.l))
    .attr('height', Y.bandwidth())
    .attr('fill', '#1a4a5c')
    .attr('rx', 3)
    .style('cursor', onClick ? 'pointer' : 'default')
    .on('click', (_, d) => onClick && onClick(d))
    .append('title').text(d => `${d[x]}: ${d[y]}`)
  svg.selectAll('label').data(data).enter().append('text')
    .attr('x', m.l - 6).attr('y', d => Y(d[x]) + Y.bandwidth() / 2 + 4)
    .attr('text-anchor', 'end').attr('font-size', 11).attr('fill', '#12202a')
    .text(d => String(d[x]).slice(0, 18))
  svg.selectAll('val').data(data).enter().append('text')
    .attr('x', d => X(d[y]) + 4).attr('y', d => Y(d[x]) + Y.bandwidth() / 2 + 4)
    .attr('font-size', 10).attr('fill', '#6b7280')
    .text(d => d[y])
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
  svg.selectAll('rect').data(data).enter().append('rect')
    .attr('x', (_, i) => X(i)).attr('y', d => Y(d.count))
    .attr('width', X.bandwidth())
    .attr('height', d => (h - m.b) - Y(d.count))
    .attr('fill', '#3d7a8c')
    .style('cursor', onClick ? 'pointer' : 'default')
    .on('click', (_, d) => onClick && onClick(d))
    .append('title').text(d => `${d.lo.toFixed(2)}–${d.hi.toFixed(2)}: ${d.count}`)
  svg.append('g').attr('transform', `translate(0,${h - m.b})`)
    .call(d3.axisBottom(X).tickFormat(i => {
      const d = data[i]
      return d ? d.lo.toFixed(0) : ''
    }).tickValues(data.map((_, i) => i).filter(i => i % Math.ceil(data.length / 6) === 0)))
    .selectAll('text').attr('font-size', 10)
}

export function heatmap(el, cells, { onClick } = {}) {
  if (!el) return
  clear(el)
  const data = cells || []
  if (!data.length) return
  const years = [...new Set(data.map(d => d.year))].sort((a, b) => a - b)
  const months = d3.range(1, 13)
  const { w } = size(el)
  const m = { t: 18, r: 12, b: 18, l: 44 }
  const cell = Math.max(10, Math.min(22, (w - m.l - m.r) / 12 - 2))
  const h = m.t + m.b + years.length * (cell + 2)
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const X = d3.scaleBand().domain(months).range([m.l, m.l + 12 * (cell + 2)]).padding(0.08)
  const Y = d3.scaleBand().domain(years).range([m.t, h - m.b]).padding(0.08)
  const max = d3.max(data, d => d.mentions) || 1
  const color = d3.scaleSequential(d3.interpolateYlGnBu).domain([0, max])
  const lookup = new Map(data.map(d => [`${d.year}-${d.month}`, d]))
  months.forEach(mo => {
    svg.append('text').attr('x', X(mo) + X.bandwidth() / 2).attr('y', 12)
      .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#6b7280')
      .text('JFMAMJJASOND'[mo - 1])
  })
  years.forEach(y => {
    svg.append('text').attr('x', m.l - 6).attr('y', Y(y) + Y.bandwidth() / 2 + 4)
      .attr('text-anchor', 'end').attr('font-size', 10).attr('fill', '#6b7280').text(y)
    months.forEach(mo => {
      const d = lookup.get(`${y}-${mo}`) || { year: y, month: mo, mentions: 0, documents: 0 }
      svg.append('rect')
        .attr('x', X(mo)).attr('y', Y(y))
        .attr('width', X.bandwidth()).attr('height', Y.bandwidth())
        .attr('rx', 2)
        .attr('fill', d.mentions ? color(d.mentions) : '#efe8d8')
        .style('cursor', d.mentions ? 'pointer' : 'default')
        .on('click', () => d.mentions && onClick && onClick(d))
        .append('title').text(`${y}-${String(mo).padStart(2, '0')}: ${d.mentions} mentions, ${d.documents} docs`)
    })
  })
}

export function bubbleMap(el, places, { onClick } = {}) {
  if (!el) return
  clear(el)
  const located = (places || []).filter(p => p.lat != null && p.lon != null)
  const { w } = size(el)
  const h = Math.max(320, Math.round(w * 0.48))
  const svg = d3.select(el).append('svg').attr('width', w).attr('height', h)
  const countries = feature(world, world.objects.countries)
  const clipped = {
    type: 'FeatureCollection',
    features: countries.features.filter(f => d3.geoCentroid(f)[1] > -58)
  }
  const projection = d3.geoMercator().fitExtent([[8, 16], [w - 8, h - 8]], clipped)
  const path = d3.geoPath(projection)
  svg.append('rect').attr('width', w).attr('height', h).attr('fill', '#dce6ea')
  svg.append('path').datum(clipped).attr('d', path).attr('fill', '#c5d0d4').attr('stroke', '#9aafb6').attr('stroke-width', 0.4)
  if (!located.length) return
  const max = d3.max(located, d => d.count) || 1
  const r = d3.scaleSqrt().domain([1, max]).range([3, 28])
  const g = svg.append('g')
  g.selectAll('circle').data(located).enter().append('circle')
    .attr('cx', d => projection([d.lon, d.lat])[0])
    .attr('cy', d => projection([d.lon, d.lat])[1])
    .attr('r', d => r(d.count))
    .attr('fill', '#1a4a5c')
    .attr('fill-opacity', 0.45)
    .attr('stroke', '#c9a227')
    .attr('stroke-width', 1)
    .style('cursor', 'pointer')
    .on('click', (_, d) => onClick && onClick(d))
    .append('title').text(d => `${d.name}: ${d.count}`)
}
