import { useState, useMemo } from 'react'
import planData from '../mocks/plan.response.json'
import './ResultsView.css'

// ── Map configuration ──────────────────────────────────────────────────────

const MAP_BOUNDS = { minLng: 117.2, maxLng: 123.8, minLat: 27.5, maxLat: 33.2 }

const MAP_CITIES = [
  { name: '上海', lng: 121.47, lat: 31.23 },
  { name: '杭州', lng: 120.15, lat: 30.26 },
  { name: '南京', lng: 118.79, lat: 32.06 },
  { name: '苏州', lng: 120.62, lat: 31.30 },
  { name: '宁波', lng: 121.54, lat: 29.87 },
  { name: '无锡', lng: 120.31, lat: 31.49 },
  { name: '扬州', lng: 119.41, lat: 32.39 },
  { name: '嘉兴', lng: 120.76, lat: 30.75 },
]

// Simplified Yangtze River waypoints for SVG polyline
const YANGTZE_POINTS = [
  [117.4, 31.9], [118.0, 32.1], [118.6, 32.0], [119.2, 32.1],
  [119.7, 32.0], [120.1, 31.9], [120.5, 31.8], [121.0, 31.7],
  [121.5, 31.5], [121.9, 31.7], [122.3, 31.8],
]

// Simplified coastline (Yangtze Delta southward)
const COAST_POINTS = [
  [122.3, 31.8], [122.0, 31.4], [121.9, 31.0], [122.0, 30.7],
  [122.1, 30.3], [121.8, 29.9], [121.9, 29.4], [121.6, 29.1],
]

// AzEl polar chart directions
const POLAR_DIRECTIONS = [
  { az: 0, label: 'N' }, { az: 90, label: 'E' },
  { az: 180, label: 'S' }, { az: 270, label: 'W' },
]

// ── Helpers ────────────────────────────────────────────────────────────────

function timeToMinutes(t) {
  if (!t) return null
  const [h, m] = t.split(':').map(Number)
  return h * 60 + (m || 0)
}

function timeToPercent(t, stripStartMin, totalMin) {
  let min = timeToMinutes(t)
  if (min === null) return null
  if (min < stripStartMin) min += 1440
  return Math.max(0, Math.min(100, ((min - stripStartMin) / totalMin) * 100))
}

function project(lng, lat, w, h) {
  const x = ((lng - MAP_BOUNDS.minLng) / (MAP_BOUNDS.maxLng - MAP_BOUNDS.minLng)) * w
  const y = ((MAP_BOUNDS.maxLat - lat) / (MAP_BOUNDS.maxLat - MAP_BOUNDS.minLat)) * h
  return { x, y }
}

function azElToXY(az, el, cx, cy, r) {
  const azRad = (az * Math.PI) / 180
  const dist = r * (1 - el / 90)
  return { x: cx + dist * Math.sin(azRad), y: cy - dist * Math.cos(azRad) }
}

function formatDateShort(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const wd = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'][d.getDay()]
  return { mm, dd, wd }
}

function cloudColor(n) {
  if (n == null) return 'var(--color-text-muted)'
  if (n <= 2) return 'var(--color-success)'
  if (n <= 5) return 'var(--color-text-secondary)'
  return 'var(--color-warning)'
}

// ── D1: 古典印刷装饰片 ────────────────────────────────────────────────────

function PrintDivider() {
  return (
    <div className="print-divider" aria-hidden="true">
      <span className="print-divider__line" />
      <span className="print-divider__cross">+</span>
      <span className="print-divider__line" />
    </div>
  )
}

// ── D3: 月相小圆 ──────────────────────────────────────────────────────────

function MoonPhase({ illumination }) {
  // illumination: 0–100
  const pct = illumination / 100
  const r = 7
  const cx = 8
  const cy = 8
  // Draw filled arc: we fill from the right if waxing, from left if waning
  // For simplicity: fill based on illumination as a lens shape
  const x1 = cx
  const y1 = cy - r
  const x2 = cx
  const y2 = cy + r
  // Terminator x offset: at 50% illumination it's a semicircle (offset=0)
  // at 100% it's full (offset=r), at 0% it's dark (offset=-r)
  const terminatorX = (pct * 2 - 1) * r
  const sweepLeft = pct > 0.5 ? 1 : 0
  const d = pct === 0
    ? ''
    : pct >= 0.99
    ? `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx} ${cy + r} A ${r} ${r} 0 1 1 ${cx} ${cy - r} Z`
    : `M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2} A ${Math.abs(terminatorX)} ${r} 0 1 ${sweepLeft} ${x1} ${y1} Z`

  return (
    <svg
      className="moon-phase"
      width="16" height="16"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(91,141,217,0.4)" strokeWidth="0.5" />
      {pct > 0.02 && (
        <path d={d} fill="rgba(91,141,217,0.3)" />
      )}
    </svg>
  )
}

// ── D2: 星等刻度条 ────────────────────────────────────────────────────────

function MagScaleBar({ value }) {
  const MIN_MAG = 0
  const MAX_MAG = 9
  const pct = ((value - MIN_MAG) / (MAX_MAG - MIN_MAG)) * 100
  const ticks = [0, 3, 6, 9]
  return (
    <span className="mag-scale" aria-hidden="true">
      <span className="mag-scale__track">
        {ticks.map((t) => (
          <span
            key={t}
            className="mag-scale__tick"
            style={{ left: `${((t - MIN_MAG) / (MAX_MAG - MIN_MAG)) * 100}%` }}
          />
        ))}
        <span className="mag-scale__cursor" style={{ left: `${pct}%` }} />
      </span>
      <span className="mag-scale__labels">
        <span>0</span>
        <span>9</span>
      </span>
    </span>
  )
}

// ── Ephemeris Strip (D4 night timeline) ────────────────────────────────────

function EphemerisStrip({ summary }) {
  const {
    sunset, civil_dusk, astro_dusk,
    target_rise, best_window,
    target_peak, moon_set,
    astro_dawn, sunrise,
  } = summary

  const STRIP_START_TIME = '17:30'
  const STRIP_END_TIME = '05:30' // next day
  const startMin = timeToMinutes(STRIP_START_TIME)
  const endMinRaw = timeToMinutes(STRIP_END_TIME) + 1440 // crosses midnight
  const totalMin = endMinRaw - startMin

  const pct = (t) => timeToPercent(t, startMin, totalMin)

  const windowStartPct = pct(best_window.start)
  const windowEndPct = pct(best_window.end)
  const moonSetPct = moon_set ? pct(moon_set) : null

  const ticks = [
    { time: sunset,      label: '日落',   labelEn: 'sunset',  type: 'solar' },
    { time: civil_dusk,  label: '民昏',   labelEn: null,      type: 'dusk' },
    { time: astro_dusk,  label: '天昏',   labelEn: null,      type: 'dusk' },
    { time: target_rise, label: '目标升起', labelEn: null,     type: 'target' },
    { time: best_window.start, label: '窗口开', labelEn: null, type: 'window' },
    { time: target_peak, label: '最高',   labelEn: null,      type: 'peak' },
    { time: best_window.end,   label: '窗口关', labelEn: null, type: 'window' },
    moon_set ? { time: moon_set, label: '月落', labelEn: null, type: 'moon' } : null,
    { time: astro_dawn,  label: '天曙',   labelEn: null,      type: 'dusk' },
    { time: sunrise,     label: '日出',   labelEn: null,      type: 'solar' },
  ].filter(Boolean)

  return (
    <div className="ephem-strip" aria-label="当夜时间轴">
      {/* Segment fills */}
      <div className="ephem-strip__track">
        {/* Window highlight */}
        <div
          className="ephem-strip__window-seg"
          style={{
            left: `${windowStartPct}%`,
            width: `${windowEndPct - windowStartPct}%`,
          }}
          aria-hidden="true"
        />
        {/* Moon-present amber line */}
        {moonSetPct !== null && (
          <div
            className="ephem-strip__moon-seg"
            style={{ left: 0, width: `${moonSetPct}%` }}
            aria-hidden="true"
          />
        )}
        {/* Window bracket markers */}
        <div
          className="ephem-strip__bracket ephem-strip__bracket--open"
          style={{ left: `${windowStartPct}%` }}
          aria-hidden="true"
        />
        <div
          className="ephem-strip__bracket ephem-strip__bracket--close"
          style={{ left: `${windowEndPct}%` }}
          aria-hidden="true"
        />
        {/* Base hairline */}
        <div className="ephem-strip__hairline" />
        {/* Ticks */}
        {ticks.map((tick) => {
          const p = pct(tick.time)
          if (p === null) return null
          return (
            <div
              key={tick.time}
              className={`ephem-strip__tick ephem-strip__tick--${tick.type}`}
              style={{ left: `${p}%` }}
            >
              <span className="ephem-strip__tick-mark" />
              <span className="ephem-strip__tick-time">{tick.time}</span>
              <span className="ephem-strip__tick-label">{tick.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Date Tabs ──────────────────────────────────────────────────────────────

function DateTabs({ dateNotes, activeDate, onDateChange }) {
  return (
    <div className="date-tabs" role="tablist" aria-label="选择观测日期">
      {dateNotes.map((note, i) => {
        const { mm, dd, wd } = formatDateShort(note.date)
        const isActive = note.date === activeDate
        const hasWarning = !!note.warning
        return (
          <button
            key={note.date}
            role="tab"
            aria-selected={isActive}
            className={[
              'date-tab',
              isActive ? 'date-tab--active' : '',
              hasWarning ? 'date-tab--warning' : '',
            ].filter(Boolean).join(' ')}
            onClick={() => onDateChange(note.date)}
            title={note.warning || undefined}
          >
            <span className="date-tab__index">0{i + 1}</span>
            <span className="date-tab__date">{mm}.{dd}</span>
            <span className="date-tab__wd">{wd}</span>
            {hasWarning && <span className="date-tab__warn-dot" aria-hidden="true" />}
          </button>
        )
      })}
    </div>
  )
}

// ── Abstract Map ──────────────────────────────────────────────────────────

function AbstractMap({ recommendations, hoveredRank, onHover, expandedRank, userLng, userLat }) {
  const W = 680
  const H = Math.round(W * (6 / 16))

  const proj = (lng, lat) => project(lng, lat, W, H)

  const yangtzeD = YANGTZE_POINTS
    .map(([lng, lat], i) => {
      const { x, y } = proj(lng, lat)
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    }).join(' ')

  const coastD = COAST_POINTS
    .map(([lng, lat], i) => {
      const { x, y } = proj(lng, lat)
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    }).join(' ')

  // Grid lines: every 1° lng and lat
  const gridLngs = Array.from({ length: Math.floor(MAP_BOUNDS.maxLng - MAP_BOUNDS.minLng) + 1 }, (_, i) => MAP_BOUNDS.minLng + i)
  const gridLats = Array.from({ length: Math.floor(MAP_BOUNDS.maxLat - MAP_BOUNDS.minLat) + 1 }, (_, i) => MAP_BOUNDS.minLat + i)

  const userPt = userLng && userLat ? proj(userLng, userLat) : null

  return (
    <div className="abstract-map" aria-label="观测地点分布图">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="abstract-map__svg">
        {/* Coordinate grid */}
        <g className="abstract-map__grid">
          {gridLngs.map((lng) => {
            const { x } = proj(lng, MAP_BOUNDS.minLat)
            return <line key={`lng-${lng}`} x1={x} y1={0} x2={x} y2={H} />
          })}
          {gridLats.map((lat) => {
            const { y } = proj(MAP_BOUNDS.minLng, lat)
            return <line key={`lat-${lat}`} x1={0} y1={y} x2={W} y2={y} />
          })}
        </g>

        {/* Rivers & coast */}
        <path d={yangtzeD} className="abstract-map__river" />
        <path d={coastD} className="abstract-map__coast" />

        {/* City labels */}
        {MAP_CITIES.map((city) => {
          const { x, y } = proj(city.lng, city.lat)
          return (
            <g key={city.name}>
              <circle cx={x} cy={y} r={1.5} className="abstract-map__city-dot" />
              <text x={x + 4} y={y + 1} className="abstract-map__city-label">{city.name}</text>
            </g>
          )
        })}

        {/* Candidate location points */}
        {recommendations.map((rec) => {
          const { x, y } = proj(rec.location.longitude, rec.location.latitude)
          const isHovered = hoveredRank === rec.rank
          const isExpanded = expandedRank === rec.rank
          const active = isHovered || isExpanded
          return (
            <g
              key={rec.rank}
              className="abstract-map__loc-group"
              onMouseEnter={() => onHover(rec.rank)}
              onMouseLeave={() => onHover(null)}
            >
              <circle
                cx={x} cy={y}
                r={active ? 9 : 6}
                className={`abstract-map__loc-ring ${active ? 'abstract-map__loc-ring--active' : ''} ${isExpanded ? 'abstract-map__loc-ring--expanded' : ''}`}
              />
              <circle
                cx={x} cy={y} r={2}
                className={`abstract-map__loc-dot ${active ? 'abstract-map__loc-dot--active' : ''}`}
              />
              <text x={x} y={y - 12} className="abstract-map__loc-label">{String(rec.rank).padStart(2, '0')}</text>
            </g>
          )
        })}

        {/* User location */}
        {userPt && (
          <g className="abstract-map__user">
            <line x1={userPt.x - 6} y1={userPt.y} x2={userPt.x + 6} y2={userPt.y} />
            <line x1={userPt.x} y1={userPt.y - 6} x2={userPt.x} y2={userPt.y + 6} />
            <text x={userPt.x + 8} y={userPt.y + 1} className="abstract-map__user-label">YOU</text>
          </g>
        )}
      </svg>
    </div>
  )
}

// ── AzEl Polar Chart ──────────────────────────────────────────────────────

function AzElPolar({ data, windowStart, windowEnd }) {
  const SIZE = 220
  const cx = SIZE / 2
  const cy = SIZE / 2
  const R = SIZE / 2 - 24

  const elevRings = [30, 60, 90]

  // Build path from data
  const points = data.map(({ az, el }) => azElToXY(az, el, cx, cy, R))
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ')

  // Window segment indices
  const wsMin = timeToMinutes(windowStart)
  const weMin = timeToMinutes(windowEnd)
  const inWindow = (t) => {
    const m = timeToMinutes(t)
    return m >= wsMin && m <= weMin
  }

  const windowPoints = []
  let inSeg = false
  for (let i = 0; i < data.length; i++) {
    const cur = data[i]
    const isIn = inWindow(cur.time)
    if (isIn && !inSeg) { inSeg = true; windowPoints.push(i > 0 ? i - 1 : i) }
    if (!isIn && inSeg) { inSeg = false; windowPoints.push(i) }
    if (isIn && i === data.length - 1) windowPoints.push(i)
  }
  const wStart = windowPoints[0] ?? null
  const wEnd = windowPoints[1] ?? windowPoints[0] ?? null
  const windowD = wStart !== null && wEnd !== null
    ? data.slice(wStart, wEnd + 1)
        .map(({ az, el }, i) => {
          const { x, y } = azElToXY(az, el, cx, cy, R)
          return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
        }).join(' ')
    : ''

  // Peak point (highest elevation)
  const peakIdx = data.reduce((best, cur, i) => cur.el > data[best].el ? i : best, 0)
  const peakPt = azElToXY(data[peakIdx].az, data[peakIdx].el, cx, cy, R)

  return (
    <svg
      className="azelpolar"
      width={SIZE} height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      aria-label="方位角/高度角随时间变化图"
    >
      {/* Elevation rings */}
      {elevRings.map((el) => {
        const r = R * (1 - el / 90)
        return (
          <circle
            key={el} cx={cx} cy={cy} r={r}
            className="azelpolar__ring"
          />
        )
      })}

      {/* Outer border ring */}
      <circle cx={cx} cy={cy} r={R} className="azelpolar__outer" />

      {/* Direction ticks & labels */}
      {Array.from({ length: 36 }, (_, i) => {
        const az = i * 10
        const azRad = (az * Math.PI) / 180
        const isMajor = az % 90 === 0
        const isMinor = az % 30 === 0
        const innerR = isMajor ? R - 7 : isMinor ? R - 4 : R - 2
        const x1 = cx + R * Math.sin(azRad)
        const y1 = cy - R * Math.cos(azRad)
        const x2 = cx + innerR * Math.sin(azRad)
        const y2 = cy - innerR * Math.cos(azRad)
        return (
          <line
            key={az}
            x1={x1.toFixed(2)} y1={y1.toFixed(2)}
            x2={x2.toFixed(2)} y2={y2.toFixed(2)}
            className={isMajor ? 'azelpolar__tick--major' : isMinor ? 'azelpolar__tick--minor' : 'azelpolar__tick--small'}
          />
        )
      })}

      {POLAR_DIRECTIONS.map(({ az, label }) => {
        const azRad = (az * Math.PI) / 180
        const labelR = R + 14
        const x = cx + labelR * Math.sin(azRad)
        const y = cy - labelR * Math.cos(azRad)
        return (
          <text key={label} x={x.toFixed(2)} y={y.toFixed(2)} className="azelpolar__dir-label">
            {label}
          </text>
        )
      })}

      {/* Elevation ring labels */}
      {elevRings.map((el) => {
        const r = R * (1 - el / 90)
        return (
          <text key={el} x={cx + 3} y={cy - r + 9} className="azelpolar__el-label">
            {el}°
          </text>
        )
      })}

      {/* Full trajectory (faint) */}
      <path d={pathD} className="azelpolar__path-full" />

      {/* Window segment (bright) */}
      {windowD && <path d={windowD} className="azelpolar__path-window" />}

      {/* Data points */}
      {data.map(({ time, az, el }, i) => {
        const { x, y } = azElToXY(az, el, cx, cy, R)
        const isWin = inWindow(time)
        return (
          <circle
            key={time}
            cx={x.toFixed(2)} cy={y.toFixed(2)}
            r={isWin ? 2.5 : 1.5}
            className={isWin ? 'azelpolar__dot--window' : 'azelpolar__dot'}
          />
        )
      })}

      {/* Peak marker */}
      <circle
        cx={peakPt.x.toFixed(2)} cy={peakPt.y.toFixed(2)}
        r={4}
        className="azelpolar__peak"
      />
      <text
        x={(peakPt.x + 7).toFixed(2)}
        y={(peakPt.y + 1).toFixed(2)}
        className="azelpolar__peak-label"
      >
        {data[peakIdx].time}
      </text>
    </svg>
  )
}

// ── Rank Badge ─────────────────────────────────────────────────────────────

function RankBadge({ rank }) {
  const cls = rank === 1 ? 'rank-badge--1' : rank === 2 ? 'rank-badge--2' : rank === 3 ? 'rank-badge--3' : 'rank-badge--other'
  return (
    <span className={`rank-badge ${cls}`} aria-label={`排名 ${rank}`}>
      {String(rank).padStart(2, '0')}
    </span>
  )
}

// ── Score Scale ────────────────────────────────────────────────────────────

function ScoreScale({ value }) {
  return (
    <span className="score-scale">
      <span className="score-scale__num">{value}</span>
      <span className="score-scale__track" aria-hidden="true">
        <span className="score-scale__fill" style={{ width: `${value}%` }} />
      </span>
    </span>
  )
}

// ── Plan Card (expanded row) ───────────────────────────────────────────────

function PlanCard({ rec, summary }) {
  const best = rec.date_comparison?.[0]?.date
    ? rec.date_comparison.reduce((a, b) => (a.weather_score >= b.weather_score ? a : b)).date
    : null

  return (
    <div className="plan-card" role="region" aria-label={`${rec.location.name} 观测方案`}>
      {/* (a) Transit */}
      <div className="plan-card__section">
        <span className="plan-card__section-label">交通路线</span>
        <div className="plan-card__transit">
          {rec.transit.options.map((opt) => (
            <div key={opt.mode} className="plan-card__route">
              <span className="plan-card__route-mode">{opt.mode}</span>
              <span className="plan-card__route-time">
                {Math.floor(opt.duration_minutes / 60)}h{opt.duration_minutes % 60 > 0 ? `${opt.duration_minutes % 60}min` : ''}
              </span>
              <span className="plan-card__route-summary">{opt.summary}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="plan-card__divider" />

      {/* (b) AzEl polar + window */}
      <div className="plan-card__section plan-card__section--row">
        <div className="plan-card__polar-wrap">
          <AzElPolar
            data={rec.azimuth_elevation}
            windowStart={summary.best_window.start}
            windowEnd={summary.best_window.end}
          />
        </div>
        <div className="plan-card__window-info">
          <span className="plan-card__section-label">建议观测窗口</span>
          <div className="plan-card__window-readout">
            <span className="plan-card__window-time">
              {summary.best_window.start}
              <span className="plan-card__window-sep"> ── </span>
              {summary.best_window.end}
            </span>
            <span className="plan-card__window-dur">
              {(() => {
                const s = timeToMinutes(summary.best_window.start)
                const e = timeToMinutes(summary.best_window.end)
                const d = e - s
                const h = Math.floor(d / 60)
                const m = d % 60
                return h > 0 ? `· ${h}h${m > 0 ? m + 'min' : ''}` : `· ${m}min`
              })()}
            </span>
          </div>
          <div className="plan-card__window-dir">
            <span className="plan-card__readout-line">
              方位 {summary.target_direction} {summary.azimuth_at_peak}°
              <span className="plan-card__dot-sep"> · </span>
              高度角 {summary.target_altitude}
            </span>
          </div>
        </div>
      </div>

      <div className="plan-card__divider" />

      {/* (d) Notes */}
      {rec.notes && (
        <div className="plan-card__section">
          <span className="plan-card__section-label">注意事项</span>
          <p className="plan-card__notes">— {rec.notes}</p>
        </div>
      )}
    </div>
  )
}

// ── Compare Table ──────────────────────────────────────────────────────────

function CompareTable({ recommendations, dateNotes, activeDate, hoveredRank, onHover, expandedRank, onExpand, activeSummary }) {
  const [sortCol, setSortCol] = useState('rank')
  const [sortAsc, setSortAsc] = useState(true)

  const recsWithDateScore = useMemo(() => {
    return recommendations.map((rec) => {
      const dc = rec.date_comparison?.find((d) => d.date === activeDate)
      return { ...rec, activeDateWeatherScore: dc?.weather_score ?? rec.weather.weather_score }
    })
  }, [recommendations, activeDate])

  const sorted = useMemo(() => {
    const arr = [...recsWithDateScore]
    arr.sort((a, b) => {
      let va, vb
      if (sortCol === 'rank')       { va = a.rank; vb = b.rank }
      else if (sortCol === 'bortle') { va = a.location.bortle; vb = b.location.bortle }
      else if (sortCol === 'transit'){ va = a.transit.options[0]?.duration_minutes ?? 9999; vb = b.transit.options[0]?.duration_minutes ?? 9999 }
      else if (sortCol === 'cloud')  { va = a.weather.cloudcover ?? 9; vb = b.weather.cloudcover ?? 9 }
      else if (sortCol === 'score')  { va = -a.overall_score; vb = -b.overall_score }
      else { va = a.rank; vb = b.rank }
      return sortAsc ? va - vb : vb - va
    })
    return arr
  }, [recsWithDateScore, sortCol, sortAsc])

  const handleSort = (col) => {
    if (sortCol === col) setSortAsc((a) => !a)
    else { setSortCol(col); setSortAsc(true) }
  }

  const SortHeader = ({ col, children }) => (
    <button
      className={`ctable__th-btn ${sortCol === col ? 'ctable__th-btn--active' : ''}`}
      onClick={() => handleSort(col)}
      type="button"
    >
      {children}
      {sortCol === col && (
        <span className="ctable__sort-arrow" aria-hidden="true">
          {sortAsc ? '↑' : '↓'}
        </span>
      )}
    </button>
  )

  return (
    <div className="ctable" role="table" aria-label="候选观测地点对比">
      {/* Header */}
      <div className="ctable__row ctable__row--head" role="row">
        <div className="ctable__th" role="columnheader"><SortHeader col="rank">#</SortHeader></div>
        <div className="ctable__th ctable__th--name" role="columnheader">地点</div>
        <div className="ctable__th" role="columnheader"><SortHeader col="bortle">Bortle</SortHeader></div>
        <div className="ctable__th ctable__th--transit" role="columnheader">交通</div>
        <div className="ctable__th" role="columnheader"><SortHeader col="transit">时长</SortHeader></div>
        <div className="ctable__th" role="columnheader"><SortHeader col="cloud">云量</SortHeader></div>
        <div className="ctable__th" role="columnheader">透明度</div>
        <div className="ctable__th" role="columnheader"><SortHeader col="score">评分</SortHeader></div>
      </div>

      {/* Rows */}
      {sorted.map((rec) => {
        const isExpanded = expandedRank === rec.rank
        const isHovered = hoveredRank === rec.rank
        const trans = rec.transit.options[0]
        const durMin = trans?.duration_minutes ?? null
        const durText = durMin ? `${Math.floor(durMin / 60)}h${durMin % 60 > 0 ? (durMin % 60) + 'm' : ''}` : '—'

        return (
          <div key={rec.rank}>
            <div
              className={[
                'ctable__row',
                isExpanded ? 'ctable__row--expanded' : '',
                isHovered ? 'ctable__row--hovered' : '',
              ].filter(Boolean).join(' ')}
              role="row"
              onClick={() => onExpand(isExpanded ? null : rec.rank)}
              onMouseEnter={() => onHover(rec.rank)}
              onMouseLeave={() => onHover(null)}
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onExpand(isExpanded ? null : rec.rank) } }}
              aria-expanded={isExpanded}
            >
              <div className="ctable__cell" role="cell">
                <RankBadge rank={rec.rank} />
              </div>
              <div className="ctable__cell ctable__cell--name" role="cell">
                <span className="ctable__loc-name">{rec.location.name}</span>
              </div>
              <div className="ctable__cell ctable__cell--mono ctable__cell--center" role="cell">
                {rec.location.bortle}
              </div>
              <div className="ctable__cell ctable__cell--transit" role="cell">
                {trans ? <span className="ctable__transit-badge">{trans.mode === '公共交通' ? '公交' : '自驾'}</span> : '—'}
              </div>
              <div className="ctable__cell ctable__cell--mono ctable__cell--right" role="cell">
                {durText}
              </div>
              <div className="ctable__cell ctable__cell--mono ctable__cell--right" role="cell"
                style={{ color: cloudColor(rec.weather.cloudcover) }}>
                {rec.weather.cloudcover != null ? `${rec.weather.cloudcover}/8` : '—'}
              </div>
              <div className="ctable__cell ctable__cell--mono ctable__cell--right" role="cell">
                {rec.weather.transparency != null ? rec.weather.transparency : '—'}
              </div>
              <div className="ctable__cell" role="cell">
                <ScoreScale value={rec.overall_score} />
              </div>
              <div className="ctable__cell ctable__cell--expand" role="cell" aria-hidden="true">
                <span className={`ctable__expand-icon ${isExpanded ? 'ctable__expand-icon--open' : ''}`} />
              </div>
            </div>

            {/* Expanded plan card */}
            {isExpanded && (
              <div className="ctable__plan-wrap">
                <PlanCard rec={rec} summary={activeSummary} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Summary Masthead ───────────────────────────────────────────────────────

function SummaryMasthead({ summary, dateStr }) {
  const { mm, dd, wd } = formatDateShort(dateStr)

  return (
    <div className="summary">
      {/* Row 1: date + magnitude */}
      <div className="summary__hero">
        <div className="summary__date-block">
          <span className="summary__date-num">{mm}.{dd}</span>
          <span className="summary__date-wd">{wd}</span>
        </div>
        <div className="summary__mag-block">
          <span className="summary__mag-val">{summary.predicted_magnitude.toFixed(1)}</span>
          <span className="summary__mag-unit">mag</span>
          <MagScaleBar value={summary.predicted_magnitude} />
        </div>
      </div>

      {/* Short hairline (排版事件, not full-width) */}
      <div className="summary__rule" aria-hidden="true" />

      {/* Row 2: readout lines */}
      <div className="summary__readouts">
        <div className="summary__readout-line">
          <MoonPhase illumination={summary.moon_illumination_percent} />
          <span className="summary__val">{summary.visibility_type === 'evening' ? '昏星' : '晨星'}</span>
          <span className="summary__sep">·</span>
          <span className="summary__val">太阳角距 {summary.solar_elongation}°</span>
          <span className="summary__sep">·</span>
          <span className="summary__val">{summary.moon_phase} {summary.moon_illumination_percent}%</span>
          <span className="summary__sep">·</span>
          <span className="summary__label">月光影响</span>
          <span className="summary__val">{summary.moon_impact}</span>
        </div>
        <div className="summary__readout-line">
          <span className="summary__label">方位</span>
          <span className="summary__val">{summary.target_direction} {summary.azimuth_at_peak}°</span>
          <span className="summary__sep">·</span>
          <span className="summary__label">高度角</span>
          <span className="summary__val">{summary.target_altitude}</span>
        </div>
        <div className="summary__readout-line summary__readout-line--window">
          <span className="summary__label">观测窗口</span>
          <span className="summary__window-val">
            {summary.best_window.start}
            <span className="summary__window-dash"> ── </span>
            {summary.best_window.end}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── ResultsView ────────────────────────────────────────────────────────────

export default function ResultsView({ event, onBack }) {
  const today = new Date()
  const metaDate = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`

  const [activeDate, setActiveDate] = useState(planData.observation_summary.best_date)
  const [expandedRank, setExpandedRank] = useState(null)
  const [hoveredRank, setHoveredRank] = useState(null)

  const activeDateNote = useMemo(
    () => planData.date_notes.find((n) => n.date === activeDate) ?? planData.date_notes[0],
    [activeDate]
  )
  const activeSummary = activeDateNote.summary

  // User location (from Shanghai as default mock)
  const userLng = 121.47
  const userLat = 31.23

  const handleExpand = (rank) => {
    setExpandedRank(rank)
  }

  return (
    <section className="results" aria-label="观测推荐结果">
      {/* Meta bar */}
      <div className="results__meta-bar" aria-hidden="true">
        <span>{metaDate}</span>
        <span>观测结果 · RESULT BRIEF</span>
      </div>

      {/* Event anchor */}
      <div className="results__anchor">
        <button className="results__back" type="button" onClick={onBack} aria-label="返回事件列表">←</button>
        <div className="results__anchor-info">
          <span className="results__anchor-name">{event?.name ?? 'C/2025 R3 彗星'}</span>
          <span className="results__anchor-tag">{event?.type === 'comet' ? '彗星' : '流星雨'}</span>
        </div>
        {event?.ephemeris && (
          <div className="results__ephem">
            r {event.ephemeris.r_au} AU · Δ {event.ephemeris.delta_au} AU
            &nbsp;· 日距角 {event.ephemeris.solar_elongation_deg}°
            &nbsp;· 高度角 {event.ephemeris.altitude_deg}°
          </div>
        )}
      </div>

      {/* D1 Divider */}
      <PrintDivider />

      {/* Summary masthead */}
      <SummaryMasthead summary={activeSummary} dateStr={activeDate} />

      {/* D1 Divider */}
      <PrintDivider />

      {/* Ephemeris strip */}
      <EphemerisStrip summary={activeSummary} />

      {/* Date tabs */}
      <DateTabs
        dateNotes={planData.date_notes}
        activeDate={activeDate}
        onDateChange={setActiveDate}
      />

      {/* Abstract map */}
      <div className="results__map-section">
        <AbstractMap
          recommendations={planData.recommendations}
          hoveredRank={hoveredRank}
          onHover={setHoveredRank}
          expandedRank={expandedRank}
          userLng={userLng}
          userLat={userLat}
        />
      </div>

      {/* Compare table */}
      <CompareTable
        recommendations={planData.recommendations}
        dateNotes={planData.date_notes}
        activeDate={activeDate}
        hoveredRank={hoveredRank}
        onHover={setHoveredRank}
        expandedRank={expandedRank}
        onExpand={handleExpand}
        activeSummary={activeSummary}
      />

      {/* D8 Page footer stamp */}
      <PrintDivider />
      <footer className="results__stamp" aria-hidden="true">
        STARGAZER · 天象观测局 · 生成于 {metaDate} · 数据源 JPL Horizons / COBS / 7Timer
      </footer>
    </section>
  )
}
