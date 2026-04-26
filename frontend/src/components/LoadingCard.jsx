/**
 * components/LoadingCard.jsx
 * Animated loading state with step-by-step status messages.
 */

export default function LoadingCard() {
  return (
    <div className="loading-card" role="status" aria-live="polite" aria-label="Loading answer">
      <div className="spinner-ring" />
      <p className="loading-text">Searching the web &amp; reasoning…</p>
      <div className="loading-steps">
        <p className="loading-step">🔍 Detecting college entities…</p>
        <p className="loading-step">🌐 Fetching real-time web data…</p>
        <p className="loading-step">🧠 Generating your answer…</p>
      </div>
    </div>
  )
}
