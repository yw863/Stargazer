import { useState } from 'react'
import EventOverview from './views/EventOverview'
import PlanningForm from './views/PlanningForm'
import ResultsView from './views/ResultsView'
import './index.css'

function App() {
  const [view, setView] = useState('overview')
  const [selectedEvent, setSelectedEvent] = useState(null)

  const handleEventSelect = (event) => {
    setSelectedEvent(event)
    setView('planning')
  }

  const handleBackToOverview = () => {
    setView('overview')
  }

  const handleSubmit = () => {
    setView('results')
  }

  return (
    <div className="app-container">
      <main className="page-main">
        {/* key 变化触发 CSS 入场动画 */}
        <div key={view} className="view-enter">
          {view === 'overview' && (
            <EventOverview onEventSelect={handleEventSelect} />
          )}
          {view === 'planning' && (
            <PlanningForm
              event={selectedEvent}
              onBack={handleBackToOverview}
              onSubmit={handleSubmit}
            />
          )}
          {view === 'results' && (
            <ResultsView onBack={handleBackToOverview} />
          )}
        </div>
      </main>
    </div>
  )
}

export default App
