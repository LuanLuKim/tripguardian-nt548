import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { early, forgetEarly } from './prefetch'
import './admin.css'

// Admin sign-in (src/analytics/auth.py): the account is ADMIN_EMAIL / ADMIN_PASSWORD from .env. The cookie is HttpOnly,
// so the page only learns whether it is signed in by asking /api/analytics/me.
type Phase = 'checking' | 'out' | 'in'

export function AdminGate({ children }: { children: (signOut: () => void) => ReactNode }) {
  const [phase, setPhase] = useState<Phase>('checking')
  const [email, setEmail] = useState('')

  useEffect(() => {
    early('me', '/api/analytics/me').then(
      async (r) => {
        if (r.ok) setEmail((await r.json()).email ?? '')
        setPhase(r.ok ? 'in' : 'out')
      },
      () => setPhase('out'),
    )
    const expired = () => setPhase('out')
    addEventListener('tg-admin-401', expired)
    return () => removeEventListener('tg-admin-401', expired)
  }, [])

  const signOut = () => {
    fetch('/api/analytics/logout', { method: 'POST' }).finally(() => setPhase('out'))
  }

  if (phase === 'checking') return <div className="admin-boot">Đang mở Admin</div>
  if (phase === 'out') return <LoginForm initial={email} onDone={(e) => (setEmail(e), setPhase('in'))} />
  return <>{children(signOut)}</>
}

function LoginForm({ initial, onDone }: { initial: string; onDone: (email: string) => void }) {
  const [email, setEmail] = useState(initial)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  let dark = false
  try {
    dark = localStorage.getItem('tg.admin.theme') === 'dark' // the pick AdminApp remembers; light otherwise
  } catch {
    /* storage blocked: light */
  }

  useEffect(() => {
    document.title = 'Đăng nhập · TripGuardian Admin'
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await fetch('/api/analytics/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.error ?? `HTTP ${r.status}`)
      forgetEarly()
      onDone(body.email ?? email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đăng nhập được')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin a-login" data-theme={dark ? 'dark' : 'light'}>
      <form className="a-card a-login__card" onSubmit={submit}>
        <h1>TripGuardian Admin</h1>
        <p className="a-small">Đăng nhập để xem dashboard.</p>
        <label>
          Email
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus={!initial} />
        </label>
        <label>
          Mật khẩu
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus={!!initial} />
        </label>
        {error && <p className="a-login__error" role="alert">{error}</p>}
        <button className="a-btn a-btn--primary" type="submit" disabled={busy}>
          {busy ? 'Đang đăng nhập' : 'Đăng nhập'}
        </button>
      </form>
    </div>
  )
}
