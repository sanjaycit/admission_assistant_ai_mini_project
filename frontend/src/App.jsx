/**
 * App.jsx — Root component
 *
 * Mental model: Input → API → Display
 * All state is local. No Redux, no Zustand.
 * UI is a thin layer; RAG decisions live in the backend.
 */

import { useState, useRef } from 'react'
import { queryRAG } from './api/query'
import SearchBox from './components/SearchBox'
import LoadingCard from './components/LoadingCard'
import ErrorCard from './components/ErrorCard'
import ResultCard from './components/ResultCard'
import HistoryList from './components/HistoryList'

export default function App() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError]         = useState(null)
  const [currentResult, setCurrentResult] = useState(null)
  const [currentQuestion, setCurrentQuestion] = useState(null)
  const [history, setHistory]     = useState([])

  // Guard against duplicate requests while one is in-flight
  const inFlight = useRef(false)

  async function handleSubmit(question) {
    if (inFlight.current) return   // prevent double-fire
    inFlight.current = true

    // Archive the current result into history before replacing it
    if (currentResult && currentQuestion) {
      setHistory((prev) => [
        ...prev,
        { id: Date.now(), question: currentQuestion, result: currentResult },
      ])
    }

    setIsLoading(true)
    setError(null)
    setCurrentResult(null)
    setCurrentQuestion(question)

    try {
      const data = await queryRAG(question)
      setCurrentResult(data)
    } catch (err) {
      setError(err.message || 'Unexpected error. Please try again.')
    } finally {
      setIsLoading(false)
      inFlight.current = false
    }
  }

  return (
    <div className="app-container">
      {/* ── Header ─────────────────────────────────────── */}
      <header className="header">
        <div className="header-logo">
          CollegeIQ
        </div>
        <p className="header-subtitle">
          Real-time AI answers for college admissions · fees · rankings · deadlines
        </p>
      </header>

      {/* ── Search Input ───────────────────────────────── */}
      <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

      {/* ── States: Loading / Error / Result ───────────── */}
      {isLoading && <LoadingCard />}

      {!isLoading && error && <ErrorCard message={error} />}

      {!isLoading && !error && currentResult && (
        <main>
          <h1 className="sr-only">Answer</h1>
          <ResultCard result={currentResult} />
        </main>
      )}

      {/* ── Empty state (first load, no query yet) ─────── */}
      {!isLoading && !error && !currentResult && history.length === 0 && (
        <div className="empty-state">
          <p className="empty-state-text">
            Ask anything about college admissions — fees, rankings, deadlines, requirements.
            The AI searches the web in real time.
          </p>
        </div>
      )}

      {/* ── Chat History ───────────────────────────────── */}
      <HistoryList history={history} />
    </div>
  )
}

/* Screen-reader only utility — keeps h1 in DOM for accessibility */
const style = document.createElement('style')
style.textContent = '.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}'
document.head.appendChild(style)
