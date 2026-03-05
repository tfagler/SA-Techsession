import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export function Dashboard({ token }: { token: string }) {
  const [sessions, setSessions] = useState<any[]>([])
  const [title, setTitle] = useState('')

  async function load() {
    const data = await api('/sessions', { token })
    setSessions(data)
  }

  async function createSession() {
    await api('/sessions', { method: 'POST', token, body: { title, description: '' } })
    setTitle('')
    await load()
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="page">
      <h2>Dashboard</h2>
      <div className="row">
        <input placeholder="New session title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button onClick={createSession}>Create</button>
      </div>
      <ul>
        {sessions.map((s) => (
          <li key={s.id}>
            <Link to={`/session/${s.id}`}>{s.title}</Link> ({s.ingest_status || 'done'})
          </li>
        ))}
      </ul>
    </div>
  )
}
