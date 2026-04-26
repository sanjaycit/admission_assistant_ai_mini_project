/**
 * api/query.js
 * Thin wrapper around the /api/query endpoint.
 * All RAG decisions stay in the backend — this is just a transport layer.
 */

const API_BASE = '/api'

/**
 * Send a question to the RAG backend.
 * @param {string} question
 * @returns {Promise<{answer: string, sources: string[], mode: string, entities: string[], is_comparison: boolean}>}
 */
export async function queryRAG(question) {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!res.ok) {
    // Attempt to extract a meaningful error message from the response
    let detail = `Server error (${res.status})`
    try {
      const json = await res.json()
      detail = json.detail || detail
    } catch (_) { /* ignore parse failures */ }
    throw new Error(detail)
  }

  return res.json()
}

/**
 * Ping the backend health endpoint.
 * @returns {Promise<boolean>}
 */
export async function pingBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' })
    return res.ok
  } catch (_) {
    return false
  }
}
