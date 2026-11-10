import { useEffect, useMemo, useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { AccountError, refreshAccount, requestResetCode, resetPassword } from '../account'
import { Icon } from '../ui/icons'
import { CALM, type Pet } from './AuthMascot'
import { badPassword, BAD_EMAIL, Banner, chars, EMAIL, PASSWORD_MAX, PASSWORD_MIN } from './AuthEmailForm'

// "Quên mật khẩu?" inside the sign-in card (docs/ACCOUNTS.md §2c): ask for a code by email, then type the 6-digit code
// with a new password. Every state has its own words and mascot mood (docs/Role_Web_Functional_Design.md §Đăng nhập);
// the server answers the same to every email, so the copy never says whether an account exists.

type Step = 'ask' | 'code'
type Problem = 'wait' | 'many' | 'off' | 'net' | 'server' | 'expired' | 'locked' | 'other'
type Field = 'email' | 'code' | 'password' | 'again'

const DIGITS = 6
const NAME_OF: Record<Field, string> = { email: 'email', code: 'mã', password: 'mật khẩu', again: 'ô nhập lại' }
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

const TEXT: Record<Exclude<Problem, 'wait'>, { title: string; text: string; say: string; retry?: boolean; again?: boolean }> = {
  many: { title: 'Bạn thử hơi nhiều lần rồi', text: 'Mình tạm dừng gửi mã từ địa chỉ này để giữ tài khoản an toàn. Bạn thử lại sau ít phút nhé.', say: 'Mình cần nghỉ một chút…' },
  off: { title: 'Chưa đặt lại mật khẩu được', text: 'Tính năng này đang tạm tắt. Bạn vào bằng Google, hoặc quay lại sau nhé.', say: 'Mình chưa gửi thư được…' },
  net: { title: 'Chưa kết nối được', text: 'Có vẻ mạng đang chập chờn. Bạn kiểm tra kết nối rồi thử lại nhé.', say: 'Mạng chập chờn rồi…', retry: true },
  server: { title: 'TripGuardian đang bận', text: 'Phía mình đang trục trặc, không phải do bạn. Thử lại sau ít phút nhé.', say: 'Mình trục trặc xíu…', retry: true },
  expired: { title: 'Mã đã hết hạn', text: 'Mã chỉ dùng được trong 10 phút và một lần. Bạn xin mã mới nhé.', say: 'Mã hết hạn mất rồi…', again: true },
  locked: { title: 'Mã này không dùng được nữa', text: 'Bạn đã nhập sai 5 lần nên mình hủy mã để giữ tài khoản an toàn. Bạn xin mã mới nhé.', say: 'Mình hủy mã này rồi…', again: true },
  other: { title: 'Chưa gửi được', text: 'Bạn kiểm tra lại các ô, hoặc tải lại trang rồi thử lần nữa nhé.', say: 'Ơ, có gì đó lạ…' },
}

// Seconds left until `until` (a timestamp), refreshed every second while it runs.
function useLeft(until: number) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (until <= Date.now()) return
    setNow(Date.now())
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [until])
  return Math.max(0, Math.ceil((until - now) / 1000))
}

// Six boxes that behave as one field: typing moves on, backspace moves back, a pasted code (or the phone's one-time-code
// autofill, which lands in one box) is spread over all of them.
function Otp({ digits, set, disabled, refs, describedBy }: { digits: string[]; set: (d: string[]) => void; disabled: boolean; refs: React.MutableRefObject<(HTMLInputElement | null)[]>; describedBy?: string }) {
  const fill = (at: number, text: string) => {
    const all = text.replace(/\D/g, '')
    const from = all.length >= DIGITS ? 0 : at // a whole code lands from the first box, wherever it was pasted
    const only = all.slice(0, DIGITS - from)
    if (!only) return
    const next = [...digits]
    for (let k = 0; k < only.length; k++) next[from + k] = only[k]
    set(next)
    const to = from + only.length
    ;(refs.current[Math.min(to, DIGITS - 1)])?.focus()
  }
  const key = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[i] && i > 0) {
      e.preventDefault()
      const next = [...digits]; next[i - 1] = ''; set(next)
      refs.current[i - 1]?.focus()
    } else if (e.key === 'ArrowLeft' && i > 0) { e.preventDefault(); refs.current[i - 1]?.focus() }
    else if (e.key === 'ArrowRight' && i < DIGITS - 1) { e.preventDefault(); refs.current[i + 1]?.focus() }
  }
  return (
    <div className="tg-auth__otp" role="group" aria-labelledby="tg-auth-code-label" aria-describedby={describedBy}>
      {digits.map((d, i) => (
        <input key={i} ref={(el) => { refs.current[i] = el }} value={d} placeholder=" " disabled={disabled}
          type="text" inputMode="numeric" pattern="[0-9]*" autoComplete={i === 0 ? 'one-time-code' : 'off'} aria-label={`Số thứ ${i + 1} trong ${DIGITS} số của mã`}
          onChange={(e) => { const v = e.target.value.replace(/\D/g, ''); if (v) fill(i, v); else { const next = [...digits]; next[i] = ''; set(next) } }}
          onKeyDown={(e) => key(i, e)} onFocus={(e) => e.target.select()}
          onPaste={(e: ClipboardEvent<HTMLInputElement>) => { e.preventDefault(); fill(i, e.clipboardData.getData('text')) }} />
      ))}
    </div>
  )
}

export function ResetFlow({ email: first, onEmail, onDone, onPet, onBack }: { email: string; onEmail: (email: string) => void; onDone: () => void; onPet: (p: Pet) => void; onBack: () => void }) {
  const [step, setStep] = useState<Step>('ask')
  const [email, setEmail] = useState(first)
  const [digits, setDigits] = useState<string[]>(Array(DIGITS).fill(''))
  const [pw, setPw] = useState('')
  const [again, setAgain] = useState('')
  const [show, setShow] = useState(false)
  const [focus, setFocus] = useState<Field | null>(null)
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({})
  const [submitted, setSubmitted] = useState(false)
  const [nudge, setNudge] = useState(false)
  const [phase, setPhase] = useState<'idle' | 'busy' | 'ok'>('idle')
  const [problem, setProblem] = useState<Problem | null>(null)
  const [wait, setWait] = useState(0) // seconds the server asked us to wait (429), for the text
  const [wrong, setWrong] = useState<number | null>(null) // tries left after a wrong code
  const [until, setUntil] = useState(0) // when another code may be asked for
  const [sentFor, setSentFor] = useState('') // the email the code was asked for
  const [remoteEmail, setRemoteEmail] = useState<string | null>(null)
  const left = useLeft(until)
  const refs = useRef<(HTMLInputElement | null)[]>([])
  const emailRef = useRef<HTMLInputElement | null>(null)
  const pwRef = useRef<HTMLInputElement | null>(null)
  const reported = useRef(false)
  const code = digits.join('')

  const mail = email.trim().toLowerCase()
  const errs: Partial<Record<Field, string>> = {}
  if (!mail) errs.email = 'Bạn nhập email nhé, mình cần để gửi mã.'
  else if (mail.length > 254 || !EMAIL.test(mail)) errs.email = BAD_EMAIL
  if (code.length < DIGITS) errs.code = 'Bạn nhập đủ 6 số trong thư nhé.'
  const n = chars(pw)
  if (!n) errs.password = `Bạn đặt mật khẩu mới nhé, ít nhất ${PASSWORD_MIN} ký tự.`
  else if (n < PASSWORD_MIN) errs.password = badPassword(n)
  else if (n > PASSWORD_MAX) errs.password = `Mật khẩu dài tối đa ${PASSWORD_MAX} ký tự.`
  if (!again) errs.again = 'Nhập lại mật khẩu một lần nữa để mình chắc bạn gõ đúng.'
  else if (again !== pw) errs.again = 'Hai mật khẩu chưa giống nhau.'
  const shown = (f: Field) => (f === 'email' && remoteEmail) || (f === 'code' && wrong !== null ? `Mã chưa đúng. Bạn còn ${wrong} lần thử.` : undefined) || (touched[f] || submitted ? errs[f] : undefined)
  const bad = (step === 'ask' ? (['email'] as Field[]) : (['code', 'password', 'again'] as Field[])).filter((f) => shown(f))
  const typing = focus === 'password' || focus === 'again'

  const pet = useMemo<Pet>(() => {
    if (phase === 'busy') return { mood: 'wait', say: '' }
    if (phase === 'ok') return { mood: 'happy', say: 'Xong rồi, chào bạn về!' }
    if (problem && problem !== 'wait') return { mood: 'sad', say: TEXT[problem].say }
    if (wrong !== null) return { mood: 'sad', say: 'Mã chưa đúng rồi…' }
    if (problem === 'wait') return { mood: 'curious', say: 'Mình vừa gửi mã xong nè.' }
    if (nudge && bad.length) return { mood: 'curious', say: `Mình thấy ${bad.map((f) => NAME_OF[f]).join(', ')} chưa ổn nè.` }
    if (step === 'code' && typing) return { mood: show ? 'peek' : 'shy', say: show ? 'Mình liếc một chút thôi nha.' : 'Bạn cứ gõ đi, mình không nhìn đâu.' }
    if (step === 'code') return { mood: 'mail', say: 'Mình gửi thư rồi, bạn kiểm tra hộp thư nhé.' }
    return { mood: 'curious', say: 'Bạn quên mật khẩu hả? Mình giúp được.' }
  }, [phase, problem, wrong, nudge, bad.join(), step, typing, show]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!reported.current && pet.mood === 'idle') return
    reported.current = true
    onPet(pet)
  }, [pet.mood, pet.say]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onPet(CALM), []) // eslint-disable-line react-hooks/exhaustive-deps

  const fail = (x: unknown): number => {
    const status = x instanceof AccountError ? x.status : 0
    setProblem(status === 429 ? ((x as AccountError).info.error === 'wait' ? 'wait' : 'many') : status === 503 ? 'off' : status >= 500 ? 'server' : status === 0 ? 'net' : 'other')
    return status
  }

  const ask = async (e?: FormEvent) => {
    e?.preventDefault()
    if (phase !== 'idle') return
    setSubmitted(true)
    setProblem(null)
    setRemoteEmail(null)
    setWrong(null)
    if (errs.email) { setNudge(true); emailRef.current?.focus(); return }
    setNudge(false)
    setPhase('busy')
    try {
      const r = await requestResetCode(email.trim())
      onEmail(email.trim())
      setSentFor(mail)
      setUntil(Date.now() + (r.resend_after ?? 60) * 1000)
      setDigits(Array(DIGITS).fill(''))
      setSubmitted(false); setTouched({}); setStep('code')
      setPhase('idle')
      window.setTimeout(() => refs.current[0]?.focus(), 50)
    } catch (x) {
      setPhase('idle')
      const status = fail(x)
      if (status === 429 && x instanceof AccountError && x.info.error === 'wait') {
        const s = Number(x.info.retry_after) || 60
        setWait(s)
        setUntil(Date.now() + Math.min(s, 60) * 1000)
      } else if (status === 400) { setProblem(null); setRemoteEmail(BAD_EMAIL); setNudge(true) }
    }
  }

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (phase !== 'idle') return
    setSubmitted(true)
    setProblem(null)
    setWrong(null)
    const miss = (['code', 'password', 'again'] as Field[]).find((f) => errs[f])
    if (miss) {
      setNudge(true)
      if (miss === 'code') refs.current[Math.min(code.length, DIGITS - 1)]?.focus()
      else (document.getElementById(`tg-auth-${miss}`) as HTMLInputElement | null)?.focus()
      return
    }
    setNudge(false)
    setPhase('busy')
    try {
      await resetPassword(sentFor || mail, code, pw)
      setPhase('ok')
      const still = matchMedia('(prefers-reduced-motion: reduce)').matches
      window.setTimeout(() => { void refreshAccount().then(onDone) }, still ? 500 : 1400)
    } catch (x) {
      setPhase('idle')
      const status = x instanceof AccountError ? x.status : 0
      const text = x instanceof AccountError ? x.message : ''
      if (status === 400 && text === 'wrong code') {
        setWrong(Number((x as AccountError).info.tries_left ?? 0))
        setDigits(Array(DIGITS).fill(''))
        window.setTimeout(() => refs.current[0]?.focus(), 50)
      } else if (status === 410) {
        setProblem(text === 'code locked' ? 'locked' : 'expired')
        setDigits(Array(DIGITS).fill(''))
        setSubmitted(false); setTouched({}); setNudge(false) // the old code is gone: the empty boxes are not an error
      } else if (status === 400 && text.startsWith('password must have')) {
        setPw(''); setAgain(''); setTouched({}); setSubmitted(false); setProblem('other')
      } else fail(x)
    }
  }

  const resend = async () => {
    if (phase !== 'idle' || left > 0) return
    setPhase('busy')
    setProblem(null)
    setWrong(null)
    try {
      const r = await requestResetCode(sentFor || mail)
      setUntil(Date.now() + (r.resend_after ?? 60) * 1000)
      setDigits(Array(DIGITS).fill(''))
      window.setTimeout(() => refs.current[0]?.focus(), 50)
    } catch (x) {
      if (fail(x) === 429 && x instanceof AccountError && x.info.error === 'wait') {
        const s = Number(x.info.retry_after) || 60
        setWait(s)
        setUntil(Date.now() + Math.min(s, 60) * 1000)
      }
    }
    setPhase('idle')
  }

  const changeEmail = () => {
    setStep('ask'); setProblem(null); setWrong(null); setSubmitted(false); setTouched({}); setNudge(false); setPw(''); setAgain('')
    window.setTimeout(() => emailRef.current?.focus(), 50)
  }

  const type = show ? 'text' : 'password'
  const eye = (
    <button type="button" className="tg-auth__eye" aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={show} disabled={phase !== 'idle'}
      onMouseDown={(e) => e.preventDefault()} onClick={() => setShow(!show)}><Icon name="eye" size={18} /></button>
  )
  const box = (f: Field, label: ReactNode, input: ReactNode, hint?: ReactNode) => {
    const msg = shown(f)
    return (
      <div className="tg-auth__f" data-bad={msg ? '' : undefined}>
        {f === 'code' ? <span className="tg-auth__otp-label" id="tg-auth-code-label">{label}</span> : <label htmlFor={`tg-auth-${f}`}>{label}</label>}
        {input}
        {msg ? <p className="tg-auth__msg" id={`tg-auth-${f}-msg`} role={f === 'code' ? 'alert' : undefined}><Icon name="warn" size={14} /><span>{msg}</span></p>
          : hint ? <p className="tg-auth__hint" id={`tg-auth-${f}-msg`}>{hint}</p> : null}
      </div>
    )
  }
  const pwAttrs = (f: 'password' | 'again', value: string, set: (v: string) => void) => ({
    id: `tg-auth-${f}`, className: 'tg-input', value, disabled: phase !== 'idle', type,
    ref: f === 'password' ? pwRef : undefined,
    onChange: (e: { target: { value: string } }) => { set(e.target.value); setNudge(false); setProblem((p) => (p === 'other' ? null : p)) },
    onFocus: () => setFocus(f),
    onBlur: () => { setFocus(null); if (value) setTouched((p) => ({ ...p, [f]: true })) },
    'aria-invalid': shown(f) ? true : undefined,
    'aria-describedby': shown(f) ? `tg-auth-${f}-msg` : undefined,
  })

  const problemBanner = () => {
    if (!problem) return null
    if (problem === 'wait') {
      const minutes = Math.ceil(wait / 60)
      return (
        <Banner title="Mình vừa gửi mã rồi"
          action={step === 'ask' ? <button type="button" className="tg-link" onClick={() => { setProblem(null); setSentFor(mail); setStep('code'); window.setTimeout(() => refs.current[0]?.focus(), 50) }}>Nhập mã mình đã nhận</button> : undefined}>
          {wait > 120 ? `Email này đã xin mã nhiều lần. Bạn thử lại sau khoảng ${minutes} phút nhé.` : left > 0 ? `Chờ ${left} giây nữa để xin mã khác. Trong lúc đó bạn cứ kiểm tra hộp thư nhé.` : 'Bạn bấm xin mã lại là được.'}
        </Banner>
      )
    }
    const p = TEXT[problem]
    return (
      <Banner title={p.title} action={p.retry ? <button type="button" className="tg-link" onClick={() => void (step === 'ask' ? ask() : submit())}>Thử lại</button>
        : p.again ? <button type="button" className="tg-link" disabled={left > 0 || phase !== 'idle'} onClick={() => void resend()}>{left > 0 ? `Gửi mã mới (sau ${left} giây)` : 'Gửi mã mới'}</button> : undefined}>{p.text}</Banner>
    )
  }

  const heading = step === 'ask'
    ? <><h1>Quên mật khẩu?</h1><p className="tg-muted">Nhập email của bạn, mình sẽ gửi một mã gồm 6 số để bạn đặt mật khẩu mới.</p></>
    : <><h1>Kiểm tra email của bạn</h1><p className="tg-muted">Nhập mã 6 số trong thư rồi đặt mật khẩu mới.</p></>

  return (
    <>
      {heading}
      {step === 'ask' ? (
        <form onSubmit={ask} noValidate aria-busy={phase === 'busy'}>
          {box('email', 'Email', <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="mail" size={20} /><input ref={emailRef} id="tg-auth-email" className="tg-input" type="email" spellCheck={false} autoComplete="email" placeholder="ban@email.com" autoFocus
            value={email} disabled={phase !== 'idle'} aria-invalid={shown('email') ? true : undefined} aria-describedby={shown('email') ? 'tg-auth-email-msg' : undefined}
            onChange={(e) => { setEmail(e.target.value); setRemoteEmail(null); setProblem(null); setNudge(false) }}
            onBlur={() => { if (email) setTouched((p) => ({ ...p, email: true })) }} /></span>)}
          {problemBanner()}
          <button type="submit" className="tg-btn tg-btn--primary tg-auth__try" disabled={phase !== 'idle'} data-phase={phase}>
            {phase === 'busy' ? <><span className="tg-auth__spin" aria-hidden="true" /> Đang gửi mã…</> : 'Gửi mã'}
          </button>
        </form>
      ) : (
        <form onSubmit={submit} noValidate aria-busy={phase === 'busy'}>
          <p className="tg-auth__sent" role="status">Nếu email này có tài khoản, mình đã gửi mã tới <strong>{sentFor || mail}</strong>. Mã có hiệu lực 10 phút. Không thấy thư thì bạn xem cả mục Spam nhé. <button type="button" className="tg-link" onClick={changeEmail} disabled={phase !== 'idle'}>Đổi email</button></p>
          {box('code', 'Mã 6 số', <Otp digits={digits} set={(d) => { setDigits(d); setWrong(null); setNudge(false); if (d.every(Boolean)) window.setTimeout(() => pwRef.current?.focus(), 30) }} disabled={phase !== 'idle'} refs={refs} describedBy={shown('code') ? 'tg-auth-code-msg' : undefined} />)}
          {box('password', 'Mật khẩu mới', <span className="tg-auth__pw tg-auth__pw--lead"><Icon name="lock" size={20} /><input {...pwAttrs('password', pw, setPw)} autoComplete="new-password" placeholder={`Ít nhất ${PASSWORD_MIN} ký tự`} />{eye}</span>,
            n > 0 ? (n < PASSWORD_MIN ? `Thêm ${PASSWORD_MIN - n} ký tự nữa là đủ.` : <><Icon name="check" size={14} /> Đủ dài rồi.</>) : null)}
          {box('again', 'Nhập lại mật khẩu mới', <input {...pwAttrs('again', again, setAgain)} autoComplete="new-password" placeholder="Gõ lại mật khẩu vừa rồi" />,
            again && again === pw ? <><Icon name="check" size={14} /> Khớp rồi.</> : null)}
          {problemBanner()}
          <button type="submit" className="tg-btn tg-btn--primary tg-auth__try" disabled={phase !== 'idle'} data-phase={phase}>
            {phase === 'busy' ? <><span className="tg-auth__spin" aria-hidden="true" /> Đang đổi mật khẩu…</>
              : phase === 'ok' ? <><Icon name="check" size={18} /> Đã đổi, đang mở…</> : 'Đổi mật khẩu và vào'}
          </button>
          {phase !== 'ok' && <p className="tg-auth__resend">
            <span>Chưa nhận được mã?</span>
            {left > 0 ? <span className="tg-auth__tick" aria-live="off">Gửi lại sau {clock(left)}</span>
              : <button type="button" className="tg-link" disabled={phase !== 'idle'} onClick={() => void resend()}>Gửi lại mã</button>}
          </p>}
        </form>
      )}
      <button type="button" className="tg-link tg-link--quiet tg-auth__back-link" onClick={onBack} disabled={phase !== 'idle'}><Icon name="arrowLeft" size={14} /> Quay lại đăng nhập</button>
    </>
  )
}
