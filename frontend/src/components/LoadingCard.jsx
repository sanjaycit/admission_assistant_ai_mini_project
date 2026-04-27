/**
 * components/LoadingCard.jsx
 * Simple loading spinner while the RAG pipeline runs.
 */

export default function LoadingCard() {
  return (
    <div className="loading-card" role="status" aria-live="polite" aria-label="Loading answer">
      <div className="spinner-ring" />
      <p className="loading-text">Generating answer…</p>
    </div>
  )
}
