import { JourneyError } from './journey'

// What a failed journey call means for the person, in plain Vietnamese. "Can't reach the server" is only said for a real network
// failure; a 429 (only after web/src/net.ts has already waited and sent it again), a replaced data version or a server fault each get their own sentence (never a raw status or error key).
export const BUSY_TEXT = 'Bạn thao tác nhanh quá, mình chưa kịp gửi hết. Bạn đợi vài giây rồi thử lại nhé.'
export const STALE_TEXT = 'Chuyến này được dựng trên bản dữ liệu địa điểm cũ, nay đã được thay bằng bản mới. Để không dùng thông tin đã lỗi thời, mình không xếp tiếp trên bản cũ. Bạn tạo lại chuyến để dùng dữ liệu mới nhé.'
const FAULT_TEXT = 'Máy chủ đang gặp trục trặc, không phải do kết nối của bạn. Bạn thử lại sau ít phút nhé.'

export const isStaleText = (t: string | null | undefined) => t === STALE_TEXT

/** `prefix` introduces a backend message that is already written for people (contains Vietnamese); `offline` is the no-network text. */
export function explainError(e: unknown, offline: string, prefix?: string): string {
  if (!(e instanceof JourneyError)) return offline
  if (e.status === 429) return BUSY_TEXT
  if (e.status === 409 && /stale_data_version/i.test(e.detail)) return STALE_TEXT
  if (e.status >= 500) return FAULT_TEXT
  const written = /[^\x00-\x7f]/.test(e.detail) ? e.detail : ''
  return written ? `${prefix ? `${prefix}: ` : ''}${written}` : 'Việc này chưa làm được lúc này. Bạn thử lại hoặc đổi cách khác nhé.'
}
