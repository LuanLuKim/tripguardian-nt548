import { useEffect, useState } from 'react'

// The wait line of a screen that loads: after `after` ms it adds one calm sentence that this is taking longer than usual.
// It never blocks anything; the skeleton under it stays and the screen shows as soon as the data arrives.
export function WaitLine({ text, after = 8000 }: { text: string; after?: number }) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), after)
    return () => clearTimeout(t)
  }, [after])
  return (
    <>
      <p className="tg-busy" role="status"><i /> {text}</p>
      {slow && <p className="tg-busy__slow" role="status">Lần này lâu hơn bình thường vì nhiều người đang dùng cùng lúc. Bạn cứ chờ thêm một chút, lựa chọn của bạn vẫn được giữ nguyên.</p>}
    </>
  )
}
