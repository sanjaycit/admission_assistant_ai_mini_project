/**
 * components/ResultCard.jsx
 * Renders the answer, source links, entity tags, and comparison badge.
 * Supports structured markdown: ## headings, - [ ] checkboxes, 1. numbered lists, **bold**
 */

import { useState } from 'react'

/* ── Inline markdown renderer (no external library) ────────────────────── */
function renderInline(text) {
  // **bold**
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

function MarkdownAnswer({ text }) {
  const [checked, setChecked] = useState({})

  const toggleCheck = (id) =>
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }))

  const lines = text.split('\n')
  const nodes = []
  let listBuffer = []   // accumulate consecutive list items
  let listType = null   // 'ul' | 'ol' | 'checklist'
  let listKey = 0

  function flushList() {
    if (!listBuffer.length) return
    if (listType === 'checklist') {
      nodes.push(
        <ul key={`list-${listKey++}`} className="md-checklist">
          {listBuffer}
        </ul>
      )
    } else if (listType === 'ol') {
      nodes.push(
        <ol key={`list-${listKey++}`} className="md-ol">
          {listBuffer}
        </ol>
      )
    } else {
      nodes.push(
        <ul key={`list-${listKey++}`} className="md-ul">
          {listBuffer}
        </ul>
      )
    }
    listBuffer = []
    listType = null
  }

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd()

    // ## Section heading
    if (/^##\s+/.test(line)) {
      flushList()
      nodes.push(
        <h3 key={idx} className="md-heading">
          {renderInline(line.replace(/^##\s+/, ''))}
        </h3>
      )
      return
    }

    // - [ ] or - [x] checkbox item
    const checkMatch = line.match(/^- \[( |x)\]\s+(.+)/)
    if (checkMatch) {
      if (listType !== 'checklist') { flushList(); listType = 'checklist' }
      const id = `chk-${idx}`
      const isChecked = checked[id] ?? (checkMatch[1] === 'x')
      listBuffer.push(
        <li key={idx} className={`md-check-item${isChecked ? ' checked' : ''}`}>
          <label className="md-check-label">
            <input
              type="checkbox"
              className="md-checkbox"
              checked={isChecked}
              onChange={() => toggleCheck(id)}
              aria-label={checkMatch[2]}
            />
            <span className="md-check-text">{renderInline(checkMatch[2])}</span>
          </label>
        </li>
      )
      return
    }

    // 1. Numbered list item
    const numMatch = line.match(/^(\d+)\.\s+(.+)/)
    if (numMatch) {
      if (listType !== 'ol') { flushList(); listType = 'ol' }
      listBuffer.push(
        <li key={idx} className="md-li">
          {renderInline(numMatch[2])}
        </li>
      )
      return
    }

    // - Bullet list item
    const bulletMatch = line.match(/^[-*]\s+(.+)/)
    if (bulletMatch) {
      if (listType !== 'ul') { flushList(); listType = 'ul' }
      listBuffer.push(
        <li key={idx} className="md-li">
          {renderInline(bulletMatch[1])}
        </li>
      )
      return
    }

    // Blank line — flush pending list, add spacing
    if (!line.trim()) {
      flushList()
      nodes.push(<div key={idx} className="md-spacer" />)
      return
    }

    // Plain paragraph
    flushList()
    nodes.push(
      <p key={idx} className="md-para">
        {renderInline(line)}
      </p>
    )
  })

  flushList()
  return <div className="md-body">{nodes}</div>
}

/* ── Sub-components ─────────────────────────────────────────────────────── */
function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="sources-card">
      <div className="sources-header">
        <span className="sources-title">Sources</span>
        <span className="sources-count">{sources.length}</span>
      </div>
      <ul className="sources-list" aria-label="Retrieved sources">
        {sources.map((url, i) => (
          <li key={i} className="source-item">
            <span className="source-num">{i + 1}</span>
            <a href={url} target="_blank" rel="noopener noreferrer"
              className="source-link" title={url}>
              {url}
            </a>
            <span className="source-ext-icon" aria-hidden="true">↗</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ── Main export ────────────────────────────────────────────────────────── */
export default function ResultCard({ result }) {
  if (!result) return null

  return (
    <div className="result-section">
      {/* Answer block */}
      <div className="answer-card">
        <div className="answer-card-header">
          <span className="answer-dot" aria-hidden="true" />
          <span className="answer-card-title">Answer</span>
        </div>
        <MarkdownAnswer text={result.answer} />
      </div>

      {/* Sources */}
      <SourcesPanel sources={result.sources} />
    </div>
  )
}
