import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import './PlanningForm.css'

// ── Constants ─────────────────────────────────────────────────────────

const TRANSPORT_OPTIONS = [
  { value: 'no_car', label: '无车' },
  { value: 'car', label: '可自驾' },
]

const EQUIPMENT_OPTIONS = [
  { value: 'naked_eye', label: '肉眼' },
  { value: 'binoculars', label: '双筒' },
  { value: 'telescope', label: '望远镜' },
]

const LOADING_STAGES = [
  { id: 'celestial', label: '解析天象参数' },
  { id: 'location',  label: '筛选观测地点' },
  { id: 'weather',   label: '查询天气与透明度' },
  { id: 'transport', label: '规划交通路线' },
]

const STAGE_DURATIONS = [4500, 4000, 8000, 5000]

// ── 城市坐标表（长三角地区）──────────────────────────────────────────

const CITY_COORDS = {
  '上海':   { lat: 31.23,  lng: 121.47 },
  '杭州':   { lat: 30.26,  lng: 120.15 },
  '南京':   { lat: 32.06,  lng: 118.79 },
  '苏州':   { lat: 31.30,  lng: 120.62 },
  '宁波':   { lat: 29.87,  lng: 121.54 },
  '无锡':   { lat: 31.49,  lng: 120.31 },
  '常州':   { lat: 31.77,  lng: 119.96 },
  '南通':   { lat: 32.01,  lng: 120.86 },
  '嘉兴':   { lat: 30.75,  lng: 120.76 },
  '绍兴':   { lat: 30.00,  lng: 120.58 },
  '湖州':   { lat: 30.89,  lng: 120.09 },
  '扬州':   { lat: 32.39,  lng: 119.41 },
  '镇江':   { lat: 32.19,  lng: 119.46 },
  '泰州':   { lat: 32.46,  lng: 119.92 },
  '台州':   { lat: 28.66,  lng: 121.43 },
  '金华':   { lat: 29.08,  lng: 119.65 },
  '衢州':   { lat: 28.94,  lng: 118.87 },
  '温州':   { lat: 28.02,  lng: 120.67 },
  '舟山':   { lat: 30.00,  lng: 122.10 },
  '合肥':   { lat: 31.82,  lng: 117.23 },
  '芜湖':   { lat: 31.33,  lng: 118.43 },
  '安庆':   { lat: 30.54,  lng: 117.05 },
  '徐州':   { lat: 34.27,  lng: 117.19 },
  '淮安':   { lat: 33.55,  lng: 119.02 },
}

function nearestCity(lat, lng) {
  let nearest = '未知位置'
  let minDist = Infinity
  for (const [city, c] of Object.entries(CITY_COORDS)) {
    const d = Math.hypot(lat - c.lat, lng - c.lng)
    if (d < minDist) { minDist = d; nearest = city }
  }
  return nearest
}

// ── Helpers ───────────────────────────────────────────────────────────

function dateOnly(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function addDays(d, n) {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

function diffDays(a, b) {
  return Math.round((dateOnly(b) - dateOnly(a)) / 86400000)
}

function fmtDate(d) {
  if (!d) return '──'
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}.${m}.${day}`
}

// ── CalendarPopover (Portal) ──────────────────────────────────────────

function CalendarPopover({ value, onChange, onClose, triggerRef }) {
  const today   = dateOnly(new Date())
  const maxDate = addDays(today, 13)

  const initStart = value[0] ? dateOnly(value[0]) : null
  const initEnd   = value[1] ? dateOnly(value[1]) : null

  const [viewMonth, setViewMonth] = useState(() => {
    const base = initStart ?? today
    return new Date(base.getFullYear(), base.getMonth(), 1)
  })
  const [start,   setStart]   = useState(initStart)
  const [end,     setEnd]     = useState(initEnd)
  const [hovered, setHovered] = useState(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  const popoverRef = useRef(null)

  // Position below trigger using fixed coords (immune to stacking contexts)
  useEffect(() => {
    if (triggerRef?.current) {
      const r = triggerRef.current.getBoundingClientRect()
      setPos({ top: r.bottom + 10, left: r.left })
    }
  }, [triggerRef])

  useEffect(() => {
    const handler = (e) => {
      const inPopover = popoverRef.current?.contains(e.target)
      const inTrigger = triggerRef?.current?.contains(e.target)
      if (!inPopover && !inTrigger) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose, triggerRef])

  const year        = viewMonth.getFullYear()
  const month       = viewMonth.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstDow    = (new Date(year, month, 1).getDay() + 6) % 7
  const totalCells  = Math.ceil((firstDow + daysInMonth) / 7) * 7

  const cells = Array.from({ length: totalCells }, (_, i) => {
    const d = i - firstDow + 1
    return d >= 1 && d <= daysInMonth ? new Date(year, month, d) : null
  })

  const handleDayClick = (day) => {
    if (!day) return
    if (day < today || day > maxDate) return
    if (!start || (start && end)) { setStart(day); setEnd(null); return }
    if (day < start) { setStart(day); setEnd(null); return }
    const delta     = diffDays(start, day)
    const clampedEnd = delta > 2 ? addDays(start, 2) : day
    setEnd(clampedEnd)
    onChange([start, clampedEnd])
    onClose()
  }

  const isDisabled = (d) => d < today || d > maxDate
  const isStart    = (d) => start && d.getTime() === start.getTime()
  const isEnd      = (d) => end   && d.getTime() === end.getTime()
  const isInRange  = (d) => {
    const rangeEnd = end || hovered
    if (!start || !rangeEnd || rangeEnd < start) return false
    return d > start && d < rangeEnd
  }

  const prevMonth  = () => setViewMonth(new Date(year, month - 1, 1))
  const nextMonth  = () => setViewMonth(new Date(year, month + 1, 1))
  const monthLabel = viewMonth.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' })

  return createPortal(
    <div
      className="cal"
      ref={popoverRef}
      role="dialog"
      aria-label="选择日期范围"
      style={{ position: 'fixed', top: pos.top, left: pos.left }}
    >
      <div className="cal__header">
        <button className="cal__nav" onClick={prevMonth} type="button" aria-label="上月">‹</button>
        <span className="cal__month">{monthLabel}</span>
        <button className="cal__nav" onClick={nextMonth} type="button" aria-label="下月">›</button>
      </div>

      <div className="cal__weekdays">
        {['一','二','三','四','五','六','日'].map((d) => (
          <span key={d} className="cal__wd">{d}</span>
        ))}
      </div>

      <div className="cal__grid">
        {cells.map((day, i) => {
          if (!day) return <span key={i} className="cal__cell cal__cell--empty" />
          const disabled = isDisabled(day)
          const isTdy    = day.getTime() === today.getTime()
          const selected = isStart(day) || isEnd(day)
          const inRange  = isInRange(day)

          return (
            <button
              key={i}
              type="button"
              className={[
                'cal__cell',
                disabled  ? 'cal__cell--disabled' : '',
                isTdy     ? 'cal__cell--today'    : '',
                selected  ? 'cal__cell--selected' : '',
                inRange   ? 'cal__cell--in-range' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => handleDayClick(day)}
              onMouseEnter={() => { if (!end) setHovered(day) }}
              onMouseLeave={() => setHovered(null)}
              disabled={disabled}
              aria-label={day.toLocaleDateString('zh-CN')}
              aria-pressed={selected}
            >
              {day.getDate()}
            </button>
          )
        })}
      </div>

      {start && !end && (
        <p className="cal__hint">再选择结束日期 · 最多 3 日</p>
      )}
    </div>,
    document.body
  )
}

// ── SegmentedControl ──────────────────────────────────────────────────

function SegmentedControl({ options, value, onChange }) {
  return (
    <div className="seg" role="group">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`seg__item ${value === opt.value ? 'seg__item--active' : ''}`}
          onClick={() => onChange(opt.value)}
          aria-pressed={value === opt.value}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ── LocationField ─────────────────────────────────────────────────────

function LocationField({ value, onChange }) {
  const [mode, setMode] = useState(value ? 'done' : 'idle')
  const [query, setQuery] = useState('')
  const [geoError, setGeoError] = useState(null)
  const inputRef = useRef(null)
  const [inputPos, setInputPos] = useState({ top: 0, left: 0, width: 0 })

  const suggestions = query.length > 0
    ? Object.keys(CITY_COORDS).filter((c) => c.includes(query))
    : []

  useEffect(() => {
    if (inputRef.current && suggestions.length > 0) {
      const r = inputRef.current.getBoundingClientRect()
      setInputPos({ top: r.bottom + 6, left: r.left, width: r.width })
    }
  }, [suggestions.length])

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError('定位不可用 · 请手动输入')
      setMode('manual')
      return
    }
    setMode('locating')
    setGeoError(null)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(4))
        const lng = parseFloat(pos.coords.longitude.toFixed(4))
        const city = nearestCity(lat, lng)
        onChange({ city, lat, lng })
        setMode('done')
      },
      () => {
        setGeoError('定位受限 · 请手动输入')
        setMode('manual')
      },
      { timeout: 8000, maximumAge: 300000 }
    )
  }, [onChange])

  const selectCity = (city) => {
    const coords = CITY_COORDS[city]
    onChange({ city, lat: coords.lat, lng: coords.lng })
    setMode('done')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && query.trim()) {
      const exact = CITY_COORDS[query.trim()]
      if (exact) {
        selectCity(query.trim())
      } else if (suggestions.length > 0) {
        selectCity(suggestions[0])
      } else {
        onChange({ city: query.trim(), lat: 31.23, lng: 121.47 })
        setMode('done')
      }
    }
  }

  if (mode === 'idle') return (
    <div className="loc-idle">
      <button className="chip chip--accent" type="button" onClick={locate}>定位</button>
      <button className="chip" type="button" onClick={() => setMode('manual')}>手动输入</button>
      {geoError && <span className="field-error">{geoError}</span>}
    </div>
  )

  if (mode === 'locating') return (
    <span className="loc-scanning">
      <span className="loc-scanning__dot" aria-hidden="true" />
      定位中
    </span>
  )

  if (mode === 'done' && value) return (
    <div className="loc-result">
      <span className="loc-result__city">{value.city}</span>
      <span className="loc-result__coords">{value.lat.toFixed(2)}°N, {value.lng.toFixed(2)}°E</span>
      <button className="chip chip--ghost" type="button"
        onClick={() => { onChange(null); setMode('idle'); setQuery('') }}>
        重新输入
      </button>
    </div>
  )

  return (
    <div className="loc-manual">
      <input
        ref={inputRef}
        className="field-input"
        type="text"
        placeholder="城市名称，如：上海"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKey}
        autoFocus
        autoComplete="off"
      />
      <span className="field-hint">输入城市名称并选择</span>
      {suggestions.length > 0 && createPortal(
        <ul className="city-sug" style={{ position: 'fixed', top: inputPos.top, left: inputPos.left, minWidth: inputPos.width }}>
          {suggestions.map((city) => (
            <li key={city}>
              <button
                type="button"
                className="city-sug__item"
                onMouseDown={(e) => { e.preventDefault(); selectCity(city) }}
              >
                <span className="city-sug__name">{city}</span>
                <span className="city-sug__coords">
                  {CITY_COORDS[city].lat.toFixed(2)}°N, {CITY_COORDS[city].lng.toFixed(2)}°E
                </span>
              </button>
            </li>
          ))}
        </ul>,
        document.body
      )}
    </div>
  )
}

// ── DateRangeField ────────────────────────────────────────────────────

function DateRangeField({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [start, end] = value
  const triggerRef = useRef(null)

  const rangeText = (() => {
    if (!start) return '选择日期范围'
    if (!end)   return `${fmtDate(start)}  ──`
    const days = diffDays(start, end) + 1
    return `${fmtDate(start)}  ─  ${fmtDate(end)}  ·  ${days}日`
  })()

  return (
    <div className="date-field">
      <button
        ref={triggerRef}
        type="button"
        className={`date-trigger ${open ? 'date-trigger--open' : ''} ${start ? 'date-trigger--filled' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="date-trigger__text">{rangeText}</span>
        <span className="date-trigger__arrow" aria-hidden="true">{open ? '↑' : '↓'}</span>
      </button>

      {open && (
        <CalendarPopover
          value={value}
          onChange={onChange}
          onClose={() => setOpen(false)}
          triggerRef={triggerRef}
        />
      )}
    </div>
  )
}

// ── LoadingProgress ───────────────────────────────────────────────────

function LoadingProgress({ onComplete }) {
  const [currentStage, setCurrentStage] = useState(0)
  const [doneStages, setDoneStages] = useState([])

  useEffect(() => {
    let cancelled = false
    const timers = []
    let cumulative = 0

    LOADING_STAGES.forEach((_, i) => {
      cumulative += STAGE_DURATIONS[i]
      const t = setTimeout(() => {
        if (cancelled) return
        setDoneStages((prev) => [...prev, i])
        if (i < LOADING_STAGES.length - 1) setCurrentStage(i + 1)
      }, cumulative)
      timers.push(t)
    })

    const done = setTimeout(() => { if (!cancelled) onComplete() }, cumulative + 700)
    timers.push(done)

    return () => { cancelled = true; timers.forEach(clearTimeout) }
  }, [onComplete])

  const totalSec = Math.round(STAGE_DURATIONS.reduce((a, b) => a + b, 0) / 1000)

  return (
    <div className="loading" aria-live="polite">
      <div className="loading__header">
        <span className="loading__title">生成观测方案</span>
        <span className="loading__status">in progress</span>
      </div>
      <div className="loading__rule" />
      <ul className="loading__stages">
        {LOADING_STAGES.map((stage, i) => {
          const done   = doneStages.includes(i)
          const active = currentStage === i && !done
          return (
            <li key={stage.id} className={[
              'lstage',
              done   ? 'lstage--done'    : '',
              active ? 'lstage--active'  : '',
              !done && !active ? 'lstage--pending' : '',
            ].filter(Boolean).join(' ')}>
              <span className="lstage__label">{stage.label}</span>
              <span className="lstage__indicator" aria-hidden="true">
                {done ? (
                  <span className="lstage__done-mark">·&thinsp;完成</span>
                ) : active ? (
                  <span className="lstage__pulse">
                    <i /><i /><i /><i />
                  </span>
                ) : (
                  <span className="lstage__queue">·&thinsp;排队</span>
                )}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="loading__rule" />
      <span className="loading__eta">预计 ~{totalSec}s</span>
    </div>
  )
}

// ── FieldRow ──────────────────────────────────────────────────────────

function FieldRow({ index, label, labelEn, filled, children, delay }) {
  return (
    <li
      className={`frow ${filled ? 'frow--filled' : 'frow--empty'}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="frow__index" aria-hidden="true">
        {String(index).padStart(2, '0')}
      </span>
      <div className="frow__body">
        <span className="frow__label">
          {label}
          {labelEn && <em className="frow__label-en">{labelEn}</em>}
        </span>
        <div className="frow__control">{children}</div>
      </div>
    </li>
  )
}

// ── PlanningForm ──────────────────────────────────────────────────────

export default function PlanningForm({ event, onBack, onSubmit }) {
  const [location,  setLocation]  = useState(null)
  const [dateRange, setDateRange] = useState([null, null])
  const [transport, setTransport] = useState(null)
  const [equipment, setEquipment] = useState('naked_eye')
  const [phase, setPhase] = useState('form') // 'form' | 'loading'

  const canSubmit = !!(location && dateRange[0] && dateRange[1] && transport)

  const handleSubmit = () => { if (canSubmit) setPhase('loading') }
  const handleComplete = useCallback(() => onSubmit(), [onSubmit])

  const today = new Date()
  const metaDate = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`

  const hintText = !location
    ? '所在位置 · 未填'
    : !dateRange[0] || !dateRange[1]
    ? '观测日期 · 未选'
    : '交通方式 · 未选'

  return (
    <section className="pform" aria-label={`观测规划 · ${event?.name ?? ''}`}>
      <div className="pform__meta-bar" aria-hidden="true">
        <span>{metaDate}</span>
        <span>观测请求 · REQUEST FORM</span>
      </div>

      <div className="pform__anchor">
        <button className="pform__back" type="button" onClick={onBack} aria-label="返回事件列表">
          ←
        </button>
        <div className="pform__anchor-info">
          <span className="pform__anchor-name">{event?.name}</span>
          <span className="pform__anchor-tag">
            {event?.type === 'comet' ? '彗星' : '流星雨'}
          </span>
        </div>
        {event?.ephemeris && (
          <div className="pform__ephem">
            r {event.ephemeris.r_au} AU · Δ {event.ephemeris.delta_au} AU
            &nbsp;· 日距角 {event.ephemeris.solar_elongation_deg}°
            &nbsp;· 高度角 {event.ephemeris.altitude_deg}°
          </div>
        )}
      </div>

      {phase === 'form' ? (
        <>
          <ul className="frow-list" role="list">
            <FieldRow index={1} label="所在位置" labelEn="LOCATION" filled={!!location} delay={60}>
              <LocationField value={location} onChange={setLocation} />
            </FieldRow>
            <FieldRow index={2} label="观测日期" labelEn="DATE RANGE" filled={!!(dateRange[0] && dateRange[1])} delay={140}>
              <DateRangeField value={dateRange} onChange={setDateRange} />
            </FieldRow>
            <FieldRow index={3} label="交通方式" labelEn="TRANSPORT" filled={!!transport} delay={220}>
              <SegmentedControl options={TRANSPORT_OPTIONS} value={transport} onChange={setTransport} />
            </FieldRow>
            <FieldRow index={4} label="观测设备" labelEn="EQUIPMENT" filled={true} delay={300}>
              <SegmentedControl options={EQUIPMENT_OPTIONS} value={equipment} onChange={setEquipment} />
            </FieldRow>
          </ul>

          <div className="pform__submit-row">
            {!canSubmit && (
              <span className="pform__hint">{hintText}</span>
            )}
            <button
              type="button"
              className={`submit-cmd ${canSubmit ? 'submit-cmd--ready' : 'submit-cmd--dim'}`}
              onClick={handleSubmit}
              disabled={!canSubmit}
              aria-disabled={!canSubmit}
            >
              <span className="submit-cmd__arrow" aria-hidden="true">→</span>
              <span>生成观测方案</span>
            </button>
          </div>
        </>
      ) : (
        <LoadingProgress onComplete={handleComplete} />
      )}
    </section>
  )
}
