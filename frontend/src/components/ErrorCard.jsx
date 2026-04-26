/**
 * components/ErrorCard.jsx
 * Surfaces backend/network errors clearly. Silent failures = worst UX.
 */

export default function ErrorCard({ message }) {
  return (
    <div className="error-card" role="alert">
      <div>
        <p className="error-title">Something went wrong</p>
        <p className="error-message">
          {message || 'Could not reach the backend. Make sure the server is running on port 8000.'}
        </p>
      </div>
    </div>
  )
}
