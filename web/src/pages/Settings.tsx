import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export function SettingsPage({ token }: { token: string }) {
  const [cheapMode, setCheapMode] = useState(false)
  const [budget, setBudget] = useState(20000)
  const [useOllama, setUseOllama] = useState(false)
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState('http://host.docker.internal:11434')
  const [ollamaModel, setOllamaModel] = useState('llama3:latest')
  const [ollamaTimeout, setOllamaTimeout] = useState(45)
  const [message, setMessage] = useState('')
  const [effective, setEffective] = useState<any>(null)
  const [crawlDefaults, setCrawlDefaults] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)

  async function load() {
    const data = await api('/settings', { token })
    setCheapMode(data.cheap_mode)
    setBudget(data.daily_hosted_token_budget)
    setUseOllama(Boolean(data.use_ollama))
    setOllamaBaseUrl(data.ollama_base_url || data.local_llm_url_effective || 'http://host.docker.internal:11434')
    setOllamaModel(data.ollama_model || data.local_llm_model_effective || 'llama3:latest')
    setOllamaTimeout(data.ollama_timeout_seconds || 45)
    setEffective({
      enabled: data.local_llm_enabled,
      url: data.local_llm_url_effective,
      model: data.local_llm_model_effective,
      timeout: data.local_llm_timeout_seconds_effective,
      source: data.local_llm_source,
    })
    setCrawlDefaults(data.crawl_defaults || null)
    setStats(data)
  }

  async function save() {
    setMessage('')
    await api('/settings', {
      method: 'PUT',
      token,
      body: {
        cheap_mode: cheapMode,
        daily_hosted_token_budget: budget,
        use_ollama: useOllama,
        ollama_base_url: ollamaBaseUrl,
        ollama_model: ollamaModel,
        ollama_timeout_seconds: ollamaTimeout,
      },
    })
    setMessage('Saved')
    await load()
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="page">
      <h2>Settings</h2>
      {effective ? (
        <div className="card">
          <div>Local LLM effective: <b>{effective.enabled ? 'enabled' : 'disabled'}</b> (source: {effective.source?.enabled})</div>
          <div>URL: <b>{effective.url}</b> (source: {effective.source?.url})</div>
          <div>Model: <b>{effective.model}</b> (source: {effective.source?.model})</div>
          <div>Timeout: <b>{effective.timeout}s</b> (source: {effective.source?.timeout_seconds})</div>
        </div>
      ) : null}
      <label>
        <input type="checkbox" checked={cheapMode} onChange={(e) => setCheapMode(e.target.checked)} />
        Cheap Mode (forces local model)
      </label>
      <input type="number" value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
      <label>
        <input type="checkbox" checked={useOllama} onChange={(e) => setUseOllama(e.target.checked)} />
        Use Local LLM (Ollama) for education output
      </label>
      <input value={ollamaBaseUrl} onChange={(e) => setOllamaBaseUrl(e.target.value)} placeholder="Ollama Base URL" />
      <input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} placeholder="Ollama Model" />
      <input type="number" value={ollamaTimeout} onChange={(e) => setOllamaTimeout(Number(e.target.value))} placeholder="Timeout seconds" />
      <button onClick={save}>Save</button>
      {message ? <div className="card">{message}</div> : null}
      {stats && (
        <div className="card">
          Today tokens in: {stats.today_tokens_in} | out: {stats.today_tokens_out}
        </div>
      )}
      {crawlDefaults ? (
        <div className="card">
          <div><b>Crawl Defaults</b></div>
          <div>depth={crawlDefaults.crawl_depth}, max_pages={crawlDefaults.max_pages}, max_links_per_page={crawlDefaults.max_links_per_page}</div>
          <div>concurrency={crawlDefaults.concurrency}, request_delay_ms={crawlDefaults.request_delay_ms}, include_pdfs={String(crawlDefaults.include_pdfs)}</div>
          <div>include_paths={crawlDefaults.include_paths || '(none)'} | exclude_paths={crawlDefaults.exclude_paths || '(none)'}</div>
        </div>
      ) : null}
    </div>
  )
}
