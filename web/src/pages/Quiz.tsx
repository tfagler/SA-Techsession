import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export function QuizPage({ token }: { token: string }) {
  const [sessions, setSessions] = useState<any[]>([])
  const [sessionId, setSessionId] = useState('')
  const [quiz, setQuiz] = useState<any>(null)
  const [mode] = useState('mcq')
  const [answers, setAnswers] = useState<any[]>([])
  const [result, setResult] = useState<any>(null)

  async function loadSessions() {
    const data = await api('/sessions', { token })
    setSessions(data)
    if (data[0]) setSessionId(String(data[0].id))
  }

  async function generateQuiz() {
    const data = await api(`/quiz/sessions/${sessionId}/generate`, { method: 'POST', token, body: { mode } })
    setQuiz(data)
    setAnswers(new Array((data.questions || []).length).fill(null))
    setResult(null)
  }

  async function submit() {
    const data = await api(`/quiz/${quiz.id}/submit`, { method: 'POST', token, body: { answers } })
    setResult(data)
  }

  useEffect(() => {
    loadSessions()
  }, [])

  return (
    <div className="page">
      <h2>Quiz</h2>
      <div className="row">
        <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>{s.title}</option>
          ))}
        </select>
        <span className="card">Mode: Multiple Choice</span>
        <button onClick={generateQuiz}>Generate</button>
      </div>

      {quiz && (
        <div>
          <h3>Questions</h3>
          {quiz.questions.map((q: any, idx: number) => (
            <div key={q.id} className="card">
              <div><b>{idx + 1}. {q.question}</b></div>
              {(q.options || []).map((opt: string, oi: number) => (
                <label key={oi} style={{ display: 'block', marginTop: '6px' }}>
                  <input
                    type="radio"
                    name={`q-${idx}`}
                    checked={answers[idx] === oi}
                    onChange={() => {
                      const next = [...answers]
                      next[idx] = oi
                      setAnswers(next)
                    }}
                  />{' '}
                  {opt}
                </label>
              ))}
            </div>
          ))}
          <button onClick={submit}>Submit Quiz</button>
        </div>
      )}

      {result && (
        <div className="card">
          <div>Score: {result.score}%</div>
          <div>{result.review?.filter((r: any) => r.is_correct).length || 0} / {result.total} correct</div>
          {(result.review || []).map((r: any, idx: number) => (
            <div key={idx} className="card">
              <div><b>{idx + 1}. {r.question}</b></div>
              <div>Status: {r.is_correct ? 'Correct' : 'Wrong'}</div>
              <div>Your answer: {r.selected !== null && r.selected !== undefined ? (r.options?.[r.selected] ?? String(r.selected)) : 'No answer'}</div>
              <div>Correct answer: {r.options?.[r.correct_answer] ?? String(r.correct_answer)}</div>
              {r.explanation ? <div>Why: {r.explanation}</div> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
