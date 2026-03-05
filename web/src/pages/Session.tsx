import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'

export function SessionPage({ token }: { token: string }) {
  const { id } = useParams()
  const [session, setSession] = useState<any>(null)
  const [url, setUrl] = useState('')
  const [sourceType, setSourceType] = useState('url')
  const [crawlDepth, setCrawlDepth] = useState(2)
  const [maxPages, setMaxPages] = useState(200)
  const [maxLinksPerPage, setMaxLinksPerPage] = useState(200)
  const [includePdfs, setIncludePdfs] = useState(true)
  const [concurrency, setConcurrency] = useState(4)
  const [requestDelayMs, setRequestDelayMs] = useState(300)
  const [includePaths, setIncludePaths] = useState('')
  const [excludePaths, setExcludePaths] = useState('')

  async function load() {
    const data = await api(`/sessions/${id}`, { token })
    setSession(data)
  }

  async function addSource() {
    const crawl_config = sourceType === 'url'
      ? {
          crawl_depth: crawlDepth,
          max_pages: maxPages,
          max_links_per_page: maxLinksPerPage,
          include_pdfs: includePdfs,
          concurrency,
          request_delay_ms: requestDelayMs,
          include_paths: includePaths,
          exclude_paths: excludePaths,
        }
      : undefined
    await api(`/sessions/${id}/sources`, { method: 'POST', token, body: { source_type: sourceType, url, crawl_config } })
    setUrl('')
    await load()
  }

  async function ingest() {
    await api(`/sessions/${id}/ingest`, { method: 'POST', token })
    await load()
  }

  async function uploadPDF(file: File) {
    const form = new FormData()
    form.append('file', file)
    await api(`/sessions/${id}/upload-pdf`, { method: 'POST', token, body: form, isForm: true })
    await load()
  }

  useEffect(() => {
    load()
  }, [id])

  useEffect(() => {
    if (!session || !['queued', 'running'].includes(session.ingest_status)) return
    const timer = setInterval(() => {
      load()
    }, 2500)
    return () => clearInterval(timer)
  }, [session?.ingest_status, id])

  if (!session) return <div className="page">Loading...</div>

  return (
    <div className="page">
      <h2>{session.title}</h2>
      <div className="card">
        Ingest status: <b>{session.ingest_status || 'unknown'}</b>
        {session.ingest_error ? <div className="error">Error: {session.ingest_error}</div> : null}
        {session.education_error ? <div className="error">Education Error: {session.education_error}</div> : null}
        <div>Pages fetched: {session.pages_fetched || 0} | skipped: {session.pages_skipped || 0} | PDFs: {session.pdfs_fetched || 0}</div>
        <div>Chunks created: {session.chunks_created || 0} | chars indexed: {session.total_chars_indexed || 0}</div>
        <div>Last URL fetched: {session.ingest_last_url || 'n/a'}</div>
        <div>Skip reasons: {JSON.stringify(session.ingest_skip_reasons || {})}</div>
      </div>
      <div className="row">
        <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
          <option value="url">Website URL</option>
          <option value="rss">RSS Feed</option>
          <option value="pdf_url">PDF URL</option>
        </select>
        <input placeholder="Source URL" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button onClick={addSource}>Add Source</button>
      </div>
      {sourceType === 'url' ? (
        <div className="card">
          <div className="row">
            <input type="number" value={crawlDepth} onChange={(e) => setCrawlDepth(Number(e.target.value))} placeholder="Crawl Depth" />
            <input type="number" value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} placeholder="Max Pages" />
            <input type="number" value={maxLinksPerPage} onChange={(e) => setMaxLinksPerPage(Number(e.target.value))} placeholder="Max Links/Page" />
          </div>
          <div className="row">
            <input type="number" value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} placeholder="Concurrency" />
            <input type="number" value={requestDelayMs} onChange={(e) => setRequestDelayMs(Number(e.target.value))} placeholder="Request Delay ms" />
            <label><input type="checkbox" checked={includePdfs} onChange={(e) => setIncludePdfs(e.target.checked)} /> Include PDFs</label>
          </div>
          <div className="row">
            <input value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} placeholder="Include path regex" />
            <input value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} placeholder="Exclude path regex" />
          </div>
        </div>
      ) : null}
      <div className="row">
        <input type="file" accept="application/pdf" onChange={(e) => e.target.files?.[0] && uploadPDF(e.target.files[0])} />
        <button onClick={ingest}>Trigger Ingest</button>
      </div>

      <h3>Sources</h3>
      <ul>
        {session.sources.map((s: any) => (
          <li key={s.id}>{s.source_type} | {s.url || s.title} | {s.status}</li>
        ))}
      </ul>

      <h3>Highlights</h3>
      <ul>
        {session.highlights.map((h: any) => (
          <li key={h.id}>
            {h.text}
            <div className="citation">{h.citation?.title} | {h.citation?.header} | {h.citation?.url}</div>
          </li>
        ))}
      </ul>

      <h3>Summary</h3>
      <div className="card">{session.education?.summary || 'No summary yet.'}</div>

      <h3>Lesson (Key Points)</h3>
      <ul>
        {(session.education?.key_points || []).map((p: string, i: number) => (
          <li key={i}>{p}</li>
        ))}
      </ul>

      <h3>Glossary</h3>
      <ul>
        {Object.entries(session.education?.glossary || {}).map(([term, def]) => (
          <li key={term}><b>{term}</b>: {String(def)}</li>
        ))}
      </ul>

      <h3>Education Quiz</h3>
      <ol>
        {(session.education?.quiz || []).map((q: any, i: number) => (
          <li key={i}>
            {q.question}
            <ul>
              {(q.options || []).map((opt: string, oi: number) => (
                <li key={oi}>{opt}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
