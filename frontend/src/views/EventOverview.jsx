import { useMemo } from 'react'
import eventsData from '../mocks/events.mock.json'
import StarField from '../components/StarField'
import './EventOverview.css'

const TYPE_LABEL = {
  comet: '彗星',
  meteor_shower: '流星雨',
}

function formatObsDate() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}.${m}.${d}`
}

function periodToShort(str) {
  const match = str.match(/(\d{4})年(\d+)月/)
  if (!match) return str
  return `${match[1]}.${match[2].padStart(2, '0')}`
}

function computeAxisProgress(periodStart, periodEnd) {
  if (!periodStart || !periodEnd) return null
  const start = new Date(periodStart).getTime()
  const end = new Date(periodEnd).getTime()
  const progress = (Date.now() - start) / (end - start)
  return Math.max(0.02, Math.min(0.98, progress))
}

function ActiveEventItem({ event, index, onEventSelect }) {
  const progress = useMemo(
    () => computeAxisProgress(event.period_start, event.period_end),
    [event.period_start, event.period_end]
  )

  const startLabel = event.period_start
    ? event.period_start.slice(0, 7).replace(/-/g, '.')
    : ''
  const endLabel = event.period_end
    ? event.period_end.slice(0, 7).replace(/-/g, '.')
    : ''

  const handleClick = () => onEventSelect(event)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onEventSelect(event)
    }
  }

  return (
    <li
      className="event-item event-item--active"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`进入 ${event.name} 观测规划`}
      style={{ animationDelay: `${80 + index * 80}ms` }}
    >
      <span className="event-item__index" aria-hidden="true">
        {String(index + 1).padStart(2, '0')}
      </span>

      <span className="event-item__name">{event.name}</span>

      <span className="event-item__type">
        {TYPE_LABEL[event.type] ?? event.type}
      </span>

      <div className="event-item__date-axis">
        <span className="event-item__date-label">{startLabel}</span>
        <div className="event-item__axis-track">
          {progress !== null && (
            <span
              className="event-item__axis-cursor"
              style={{ left: `${progress * 100}%` }}
              aria-hidden="true"
            />
          )}
        </div>
        <span className="event-item__date-label">{endLabel}</span>
      </div>

      <div className="event-item__summary-row">
        <span className="event-item__pulse-dot" aria-hidden="true" />
        <span className="event-item__summary">{event.current_summary}</span>
      </div>

      <span className="event-item__arrow" aria-hidden="true">→</span>

      {event.ephemeris && (
        <div className="event-item__ephemeris">
          r {event.ephemeris.r_au} AU · Δ {event.ephemeris.delta_au} AU
          &nbsp;· 日距角 {event.ephemeris.solar_elongation_deg}°
          &nbsp;· 高度角 {event.ephemeris.altitude_deg}°
        </div>
      )}
    </li>
  )
}

function UpcomingEventItem({ event, displayIndex, staggerIndex }) {
  return (
    <li
      className="event-item event-item--upcoming"
      aria-disabled="true"
      style={{ animationDelay: `${80 + staggerIndex * 80}ms` }}
    >
      <span className="event-item__index" aria-hidden="true">
        {String(displayIndex + 1).padStart(2, '0')}
      </span>

      <div className="event-item__upcoming-row">
        <span className="event-item__period-short">
          {periodToShort(event.best_period)}
        </span>
        <span className="event-item__name">{event.name}</span>
      </div>

      <span className="event-item__type">
        {TYPE_LABEL[event.type] ?? event.type}
      </span>
    </li>
  )
}

export default function EventOverview({ onEventSelect }) {
  const { events } = eventsData
  const activeEvents = events.filter((e) => e.status === 'active')
  const upcomingEvents = events.filter((e) => e.status === 'coming_soon')

  const comet = activeEvents.find((e) => e.type === 'comet' && e.comet_ra)
  const cometRa = comet?.comet_ra ?? 130.5
  const cometDec = comet?.comet_dec ?? 19.8

  return (
    <section className="overview" aria-label="近期天文事件">
      <StarField cometRa={cometRa} cometDec={cometDec} />

      <div className="overview__content">
        <div className="overview__meta-bar" aria-hidden="true">
          <span>{formatObsDate()}</span>
          <span>长三角 · 天象概览</span>
        </div>

        <p className="overview__eyebrow">Do Look Up ——</p>
        <h1 className="overview__heading">近日可见：</h1>

        <ul className="event-list" role="list">
          {activeEvents.map((event, i) => (
            <ActiveEventItem
              key={event.event_id}
              event={event}
              index={i}
              onEventSelect={onEventSelect}
            />
          ))}
        </ul>

        {upcomingEvents.length > 0 && (
          <>
            <div
              className="upcoming-header"
              aria-hidden="true"
              style={{
                animationDelay: `${80 + activeEvents.length * 80 + 40}ms`,
              }}
            >
              <span className="upcoming-header__label">排程 · upcoming</span>
            </div>
            <ul className="event-list event-list--upcoming" role="list">
              {upcomingEvents.map((event, i) => (
                <UpcomingEventItem
                  key={event.event_id}
                  event={event}
                  displayIndex={activeEvents.length + i}
                  staggerIndex={activeEvents.length + i + 1}
                />
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  )
}
