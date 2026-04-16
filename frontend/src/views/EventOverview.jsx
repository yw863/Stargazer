import eventsData from '../mocks/events.mock.json'
import './EventOverview.css'

/* 事件类型中文映射 */
const TYPE_LABEL = {
  comet: '彗星',
  meteor_shower: '流星雨',
}

/* 当前日期，仪器读数格式：2026.04.15 */
function formatObsDate() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}.${m}.${d}`
}

function EventItem({ event, index, onEventSelect }) {
  const isActive = event.status === 'active'

  const handleClick = () => {
    if (isActive) onEventSelect(event)
  }

  const handleKeyDown = (e) => {
    if (isActive && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      onEventSelect(event)
    }
  }

  return (
    <li
      className={`event-item ${isActive ? 'event-item--active' : 'event-item--coming-soon'}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={isActive ? 'button' : undefined}
      tabIndex={isActive ? 0 : undefined}
      aria-label={isActive ? `进入 ${event.name} 观测规划` : undefined}
      aria-disabled={!isActive ? 'true' : undefined}
    >
      {/* 序号（星历表式） */}
      <span className="event-item__index" aria-hidden="true">
        {String(index + 1).padStart(2, '0')}
      </span>

      {/* 名称 */}
      <span className="event-item__name">{event.name}</span>

      {/* 类型标签 */}
      <span className="event-item__type">
        {TYPE_LABEL[event.type] ?? event.type}
      </span>

      {/* 最佳时段 */}
      <span className="event-item__period">{event.best_period}</span>

      {/* 状态描述 或 即将上线 */}
      {isActive && event.current_summary ? (
        <span className="event-item__summary">{event.current_summary}</span>
      ) : (
        <span className="event-item__coming-soon-label">即将上线</span>
      )}

      {/* 指示符：active → 进入箭头；coming-soon → 锁定圆圈 */}
      {isActive ? (
        <span className="event-item__arrow" aria-hidden="true">→</span>
      ) : (
        <span className="event-item__lock" aria-hidden="true">○</span>
      )}
    </li>
  )
}

export default function EventOverview({ onEventSelect }) {
  const { events } = eventsData

  return (
    <section className="overview" aria-label="近期天文事件">
      {/* 仪器读数 meta bar */}
      <div className="overview__meta-bar" aria-hidden="true">
        <span>{formatObsDate()}</span>
        <span>长三角 · 天象概览</span>
      </div>

      {/* 页头 */}
      <p className="overview__eyebrow">Do Look Up——</p>
      <h1 className="overview__heading">近日可见：</h1>

      {/* 事件列表 */}
      <ul className="event-list" role="list">
        {events.map((event, i) => (
          <EventItem
            key={event.event_id}
            event={event}
            index={i}
            onEventSelect={onEventSelect}
          />
        ))}
      </ul>
    </section>
  )
}
