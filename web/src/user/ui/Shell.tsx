import { useEffect, type ReactNode } from 'react'

export function Page({ children, className = '', narrow = false }: { children: ReactNode; className?: string; narrow?: boolean }) {
  return <div className={`tg-page ${narrow ? 'is-narrow' : ''} ${className}`}>{children}</div>
}

export function useTitle(t: string) {
  useEffect(() => { document.title = `${t} · TripGuardian` }, [t])
}
