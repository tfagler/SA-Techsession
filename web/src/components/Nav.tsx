import { Link } from 'react-router-dom'

export function Nav({ onLogout }: { onLogout: () => void }) {
  return (
    <nav className="nav">
      <Link to="/dashboard">Dashboard</Link>
      <Link to="/quiz">Quiz</Link>
      <Link to="/settings">Settings</Link>
      <button onClick={onLogout}>Logout</button>
    </nav>
  )
}
