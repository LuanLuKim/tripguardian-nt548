import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { AccountError, loginWithEmail, refreshAccount, registerWithEmail } from '../account'
import { Icon } from '../ui/icons'
import { CALM, type Pet } from './AuthMascot'

// Sign up (name, email, password, repeat) or sign in (email, password) without Google. Every state the visitor can
// reach has its own screen: per-field messages (checked here with the server's own rules, then again by the server),
// and one banner for what only the server can say. docs/Role_Web_Functional_Design.md §Đăng nhập maps each to a response.

type Field = 'name' | 'email' | 'password' | 'again'
type Values = Record<Field, string>
type Problem = 'wrong' | 'many' | 'net' | 'server' | 'other'
type Remote = Partial<Record<Field, { text: string; taken?: boolean }>>

const ORDER: Field[] = ['name', 'email', 'password', 'again']
export const EMAIL = /^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$/ // src/accounts/service.py EMAIL
export const PASSWORD_MIN = 8
export const PASSWORD_MAX = 128
export const chars = (s: string) => [...s].length
const NAME_OF: Record<Field, string> = { name: 'tên', email: 'email', password: 'mật khẩu', again: 'ô nhập lại' }

export const BAD_EMAIL = 'Email này nhìn chưa đúng. Thử dạng ban@email.com nhé.'
export const badPassword = (n: number) => `Mật khẩu cần ít nhất ${PASSWORD_MIN} ký tự, bạn còn thiếu ${PASSWORD_MIN - n}.`

function check(v: Values, up: boolean): Partial<Record<Field, string>> {
  const e: Partial<Record<Field, string>> = {}
  const mail = v.email.trim().toLowerCase()
  if (!mail) e.email = up ? 'Bạn nhập email nhé, đây là tên đăng nhập của bạn.' : 'Bạn nhập email nhé, mình cần để tìm tài khoản.'
  else if (mail.length > 254 || !EMAIL.test(mail)) e.email = BAD_EMAIL
  const n = chars(v.password)
  if (!n) e.password = up ? `Bạn đặt một mật khẩu nhé, ít nhất ${PASSWORD_MIN} ký tự.` : 'Bạn chưa nhập mật khẩu.'
  else if (up && n < PASSWORD_MIN) e.password = badPassword(n)
  else if (up && n > PASSWORD_MAX) e.password = `Mật khẩu dài tối đa ${PASSWORD_MAX} ký tự.`
  if (up) {
    if (!v.again) e.again = 'Nhập lại mật khẩu một lần nữa để mình chắc bạn gõ đúng.'
    else if (v.again !== v.password) e.again = 'Hai mật khẩu chưa giống nhau.'
  }
  return e
}

const PROBLEMS: Record<Problem, { title: string; text: string; say: string; retry?: boolean }> = {
  wrong: { title: 'Email hoặc mật khẩu chưa khớp', text: 'Bạn gõ lại giúp mình nhé. Nếu trước đó bạn vào bằng Google, hãy bấm nút Google bên dưới.', say: 'Ối, chưa khớp rồi…' },
  many: { title: 'Bạn thử hơi nhiều lần rồi', text: 'Mình tạm dừng đăng nhập với email này để giữ tài khoản an toàn. Chờ vài phút rồi thử lại, hoặc vào bằng Google trong lúc đợi.', say: 'Mình cần nghỉ một chút…' },
  net: { title: 'Chưa kết nối được', text: 'Có vẻ mạng đang chập chờn. Bạn kiểm tra kết nối rồi thử lại nhé.', say: 'Mạng chập chờn rồi…', retry: true },
  server: { title: 'TripGuardian đang bận', text: 'Phía mình đang trục trặc, không phải do bạn. Thử lại sau ít phút nhé.', say: 'Mình trục trặc xíu…', retry: true },
  other: { title: 'Chưa gửi được', text: 'Bạn kiểm tra lại các ô, hoặc tải lại trang rồi thử lần nữa nhé.', say: 'Ơ, có gì đó lạ…' },
}

// What the server said about one field (400 / 409 of POST /api/auth/register), by its `error` text (src/accounts/service.py).
function remoteField(status: number, message: string): Remote | null {
  if (status === 409) return { email: { text: 'Email này đã có tài khoản rồi.', taken: true } }
  if (status !== 400) return null
  if (message.startsWith('email is not valid')) return { email: { text: BAD_EMAIL } }
  if (message.startsWith('password must have')) return { password: { text: `Mật khẩu cần từ ${PASSWORD_MIN} đến ${PASSWORD_MAX} ký tự.` } }
  if (message.startsWith('name is too long')) return { name: { text: 'Tên hơi dài, bạn rút gọn dưới 60 ký tự nhé.' } }
  return null
}

export const list = (items: string[]) => (items.length < 2 ? items[0] ?? '' : `${items.slice(0, -1).join(', ')} và ${items[items.length - 1]}`)

export function Banner({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="tg-auth__banner" role="alert">
      <Icon name="warn" size={18} />
      <div><strong>{title}</strong><p>{children}</p>{action}</div>
    </div>
  )
}

// onForgot: the sign-in form offers "Quên mật khẩu?" next to the password label (only when the server can mail a code);
// it carries the email typed so far into the reset panel, and `email` brings it back.
export function EmailForm({ up, onDone, onPet, onSwitch, onForgot, email = '' }: { up: boolean; onDone: () => void; onPet: (p: Pet) => void; onSwitch: () => void; onForgot?: (email: string) => void; email?: string }) {
  const [v, setV] = useState<Values>({ name: '', email, password: '', again: '' })
  const [show, setShow] = useState(false)
  const [focus, setFocus] = useState<Field | null>(null)
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({})
  const [submitted, setSubmitted] = useState(false)
  const [nudge, setNudge] = useState(false) // a submit was refused for missing or wrong input, until the next keystroke
  const [phase, setPhase] = useState<'idle' | 'busy' | 'ok'>('idle')
  const [problem, setProblem] = useState<Problem | null>(null)
  const [remote, setRemote] = useState<Remote>({})
  const refs = useRef<Partial<Record<Field, HTMLInputElement | null>>>({})
  const reported = useRef(false)
  const later = useRef<Field | null>(null) // a field to focus once the form is enabled again
  useEffect(() => { if (phase === 'idle' && later.current) { refs.current[later.current]?.focus(); later.current = null } }, [phase])

  // Another mode is another form: its messages go, what was typed stays.
  useEffect(() => { setTouched({}); setSubmitted(false); setNudge(false); setProblem(null); setRemote({}) }, [up])

  const errs = check(v, up)
  const seen = (f: Field) => remote[f]?.text ?? (touched[f] || submitted ? errs[f] : undefined)
  const set = (f: Field, value: string) => {
    setV((p) => ({ ...p, [f]: value }))
    setRemote((p) => (p[f] ? { ...p, [f]: undefined } : p))
    setProblem(null)
    setNudge(false)
  }
  const bad = ORDER.filter((f) => (up || f === 'email' || f === 'password') && seen(f))
  const typing = focus === 'password' || focus === 'again'

  const pet = useMemo<Pet>(() => {
    if (phase === 'busy') return { mood: 'wait', say: '' }
    if (phase === 'ok') return { mood: 'happy', say: up ? 'Chào bạn mới nhé!' : 'Chào mừng bạn về!' }
    if (problem) return { mood: 'sad', say: PROBLEMS[problem].say }
    if (remote.email?.taken) return { mood: 'curious', say: 'Email này mình nhận ra rồi nè!' }
    if (nudge && bad.length) return { mood: 'curious', say: `Mình thấy ${list(bad.map((f) => NAME_OF[f]))} chưa ổn nè.` }
    if (typing) return { mood: show ? 'peek' : 'shy', say: show ? 'Mình liếc một chút thôi nha.' : 'Bạn cứ gõ đi, mình không nhìn đâu.' }
    return CALM
  }, [phase, problem, remote.email?.taken, nudge, bad.join(), typing, show, up]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!reported.current && pet.mood === 'idle') return // keep a mood the screen opened with (a Google error)
    reported.current = true
    onPet(pet)
  }, [pet.mood, pet.say]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (phase !== 'idle') return
    setSubmitted(true)
    setProblem(null)
    const first = ORDER.find((f) => errs[f] && (up || f === 'email' || f === 'password'))
    if (first) { setNudge(true); refs.current[first]?.focus(); return }
    setPhase('busy')
    try {
      const mail = v.email.trim()
      await (up ? registerWithEmail(mail, v.password, v.name) : loginWithEmail(mail, v.password))
      setPhase('ok')
      const still = matchMedia('(prefers-reduced-motion: reduce)').matches
      window.setTimeout(() => { void refreshAccount().then(onDone) }, still ? 500 : 1400) // the hop is seen before the app opens
    } catch (x) {
      setPhase('idle')
      const status = x instanceof AccountError ? x.status : 0
      const field = x instanceof AccountError ? remoteField(status, x.message) : null
      if (field) {
        setRemote(field)
        const f = ORDER.find((k) => field[k])
        setNudge(true)
        later.current = f ?? null
      } else {
        setProblem(status === 401 ? 'wrong' : status === 429 ? 'many' : status >= 500 ? 'server' : status === 0 ? 'net' : 'other')
        if (status === 401) { setV((p) => ({ ...p, password: '' })); setTouched({}); setSubmitted(false); later.current = 'password' }
      }
    }
  }

  const field = (f: Field, label: string, input: ReactNode, hint?: ReactNode, aside?: ReactNode) => {
    const msg = seen(f)
    return (
      <div className="tg-auth__f" data-bad={msg ? '' : undefined}>
        {aside ? <div className="tg-auth__lrow"><label htmlFor={`tg-auth-${f}`}>{label}</label>{aside}</div> : <label htmlFor={`tg-auth-${f}`}>{label}</label>}
        {input}
        {msg ? (
          <p className="tg-auth__msg" id={`tg-auth-${f}-msg`}>
            <Icon name="warn" size={14} />
            <span>{msg}{remote[f]?.taken && <span className="tg-auth__sub"><button type="button" className="tg-link" onClick={onSwitch}>Đăng nhập bằng email này</button> nhé. Nếu trước đó bạn vào bằng Google, hãy bấm nút Google bên dưới.</span>}</span>
          </p>
        ) : hint ? <p className="tg-auth__hint" id={`tg-auth-${f}-msg`}>{hint}</p> : null}
      </div>
    )
  }
  const attrs = (f: Field) => ({
    id: `tg-auth-${f}`, className: 'tg-input', value: v[f], disabled: phase !== 'idle',
    ref: (el: HTMLInputElement | null) => { refs.current[f] = el },
    onChange: (e: { target: { value: string } }) => set(f, e.target.value),
    onFocus: () => setFocus(f),
    onBlur: () => { setFocus(null); if (v[f]) setTouched((p) => ({ ...p, [f]: true })) }, // an empty field is only called out on submit: no jumping layout under a click
    'aria-invalid': seen(f) ? true : undefined,
    'aria-describedby': seen(f) || (f === 'again' && v.again && v.again === v.password) || (f === 'password' && up && v.password) ? `tg-auth-${f}-msg` : undefined,
  })
  const n = chars(v.password)
  const type = show ? 'text' : 'password'
  const eye = (
    <button type="button" className="tg-auth__eye" aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={show} disabled={phase !== 'idle'}
      onMouseDown={(e) => e.preventDefault() /* keep the typing focus: the mascot should not look up mid-word */} onClick={() => setShow(!show)}><Icon name="eye" size={18} /></button>
  )
  const p = PROBLEMS[problem ?? 'other']
  return (
    <form onSubmit={submit} noValidate aria-busy={phase === 'busy'}>
      {up && field('name', 'Tên của bạn', <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="user" size={20} /><input {...attrs('name')} maxLength={60} autoComplete="name" placeholder="Không bắt buộc" /></span>)}
      {field('email', 'Email', <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="mail" size={20} /><input {...attrs('email')} type="email" spellCheck={false} autoComplete="email" placeholder="ban@email.com" autoFocus /></span>)}
      {field('password', 'Mật khẩu',
        <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="lock" size={20} /><input {...attrs('password')} type={type} autoComplete={up ? 'new-password' : 'current-password'} placeholder={up ? `Ít nhất ${PASSWORD_MIN} ký tự` : 'Nhập mật khẩu'} />{eye}</span>,
        up && n > 0 ? (n < PASSWORD_MIN ? `Thêm ${PASSWORD_MIN - n} ký tự nữa là đủ.` : <><Icon name="check" size={14} /> Đủ dài rồi.</>) : null,
        !up && onForgot ? <button type="button" className="tg-link tg-auth__forgot" disabled={phase !== 'idle'} onMouseDown={(e) => e.preventDefault() /* no blur: an email message appearing under the click must not move the link */} onClick={() => onForgot(v.email.trim())}>Quên mật khẩu?</button> : null)}
      {up && field('again', 'Nhập lại mật khẩu', <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="lock" size={20} /><input {...attrs('again')} type={type} autoComplete="new-password" placeholder="Gõ lại mật khẩu vừa rồi" /></span>,
        v.again && v.again === v.password ? <><Icon name="check" size={14} /> Khớp rồi.</> : null)}
      {problem && (
        <Banner title={p.title} action={p.retry ? <button type="button" className="tg-link" onClick={() => void submit()}>Thử lại</button> : undefined}>{p.text}</Banner>
      )}
      <button type="submit" className="tg-btn tg-btn--primary tg-auth__try" disabled={phase !== 'idle'} data-phase={phase}>
        {phase === 'busy' ? <><span className="tg-auth__spin" aria-hidden="true" /> {up ? 'Đang tạo tài khoản…' : 'Đang đăng nhập…'}</>
          : phase === 'ok' ? <><Icon name="check" size={18} /> {up ? 'Tài khoản đã sẵn sàng' : 'Vào rồi, đang mở…'}</>
          : up ? 'Tạo tài khoản' : 'Đăng nhập'}
      </button>
    </form>
  )
}
