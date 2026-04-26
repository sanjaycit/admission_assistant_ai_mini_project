/**
 * components/HistoryList.jsx
 * Renders previous Q&A pairs in a collapsible chat-style list.
 */

export default function HistoryList({ history }) {
  if (!history || history.length === 0) return null

  // Show in reverse so newest is at top, but only past items (not current)
  const past = [...history].reverse()

  return (
    <section className="history-section" aria-label="Previous queries">
      <h2 className="history-heading">Previous queries</h2>
      {past.map((item, i) => (
        <div key={item.id} className="history-item">
          <div className="history-question">
            <span className="history-q-icon" aria-hidden="true">Q</span>
            {item.question}
          </div>
          <div className="history-answer">{item.result.answer}</div>
          <div className="history-answer-meta">
            {item.result.mode === 'web'
              ? <span className="badge badge-mode-web">Live Web</span>
              : <span className="badge badge-mode-cache">Cache</span>
            }
            {item.result.is_comparison && (
              <span className="badge badge-comparison">Comparison</span>
            )}
          </div>
        </div>
      ))}
    </section>
  )
}
