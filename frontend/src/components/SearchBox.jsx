/**
 * components/SearchBox.jsx
 * Input box + submit button + suggestion chips.
 */

import { useState, useRef } from 'react'

const SUGGESTIONS = [
  'What are the eligibility criteria for VIT Vellore?',
  'What documents are required to apply to VIT?',
  'What is the application deadline for VIT 2025?',
  'What is the tuition fee for VIT Chennai?',
  'How to apply to VIT step by step?',
]

export default function SearchBox({ onSubmit, isLoading }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  function handleKeyDown(e) {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleInput(e) {
    setValue(e.target.value)
    // Auto-grow textarea
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  function fillSuggestion(text) {
    setValue(text)
    textareaRef.current?.focus()
  }

  return (
    <section className="search-section">
      <label className="search-label" htmlFor="query-input">
        Ask about admissions
      </label>

      <div className="search-input-row">
        <textarea
          id="query-input"
          ref={textareaRef}
          className="search-input"
          rows={1}
          placeholder="e.g. What are the eligibility criteria for VIT Vellore?"
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          aria-label="Your question"
        />
        <button
          id="submit-btn"
          className="search-btn"
          onClick={handleSubmit}
          disabled={isLoading || !value.trim()}
          aria-label="Submit question"
        >
          {isLoading ? (
            <>
              <span className="spinner-ring" style={{ width: 18, height: 18, borderWidth: 2 }} />
              Searching…
            </>
          ) : (
            <>
              <span aria-hidden="true">✦</span>
              Ask AI
            </>
          )}
        </button>
      </div>

      <div className="search-suggestions" role="list" aria-label="Suggested questions">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            className="suggestion-chip"
            onClick={() => fillSuggestion(s)}
            disabled={isLoading}
            role="listitem"
          >
            {s}
          </button>
        ))}
      </div>
    </section>
  )
}
