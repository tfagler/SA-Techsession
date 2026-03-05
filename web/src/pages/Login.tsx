import { useState } from 'react'
import { api } from '../lib/api'

export function Login({ onAuth }: { onAuth: (token: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(path: '/auth/login' | '/auth/register') {
    try {
      setError('')
      const data = await api(path, { method: 'POST', body: { email, password } })
      onAuth(data.access_token)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="page">
      <h1>Study Sessions</h1>
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <div className="row">
        <button onClick={() => submit('/auth/login')}>Login</button>
        <button onClick={() => submit('/auth/register')}>Register</button>
      </div>
      <p className="error">{error}</p>
    </div>
  )
}
