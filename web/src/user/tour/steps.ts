// The tour's script (it starts on the home page; the sign-in screen is not part of it): chapters of stops, each stop = one real element (data-tour="<target>"), a pose of the acorn and a line.
// The words are fixed text in the product's voice ("mình" / "bạn"), never model output. Spec: docs/plans/2026-10-31-guided-tour-design.md §5.
export type Pose =
  | 'idle' | 'curious' | 'wait' | 'happy' | 'shy' | 'mail' | 'sad'
  | 'wave' | 'wow' | 'wink' | 'love' | 'cheer' | 'bow' | 'point' | 'point_up' | 'walk_a' | 'walk_b'

export type Kind = 'guest' | 'member'

export type Step = {
  id: string
  route?: string // the page this stop lives on, when it differs from its chapter's
  target?: string // data-tour id of the lit element; none = the mascot stands mid-screen
  pose: Pose
  say: string
  guestSay?: string // said instead of `say` to a guest, for what needs an account
  cta?: 'done' | 'create' // "Xong" (celebrate) · "Tạo chuyến đi"
}
export type Chapter = { id: string; title: string; route: string | null; steps: Step[] } // route: where the page must be (null = stay)

const INVITE = 'Đăng nhập để hưởng đầy đủ quyền lợi nhé!'

// Each line is one short idea (the bubble is read at a glance, two lines at most).
const HOME: Chapter = {
  id: 'home', title: 'Trang chủ', route: '/app',
  steps: [
    { id: 'home-hi', pose: 'wave', say: 'Chào bạn! Mình dẫn bạn đi một vòng nhé.' },
    { id: 'home-search', target: 'search', pose: 'point', say: 'Gõ chuyến bạn muốn đi ở đây. Phím / để nhảy nhanh tới.' },
    { id: 'home-hero', target: 'hero', pose: 'wow', say: 'Mọi nơi ở đây đều có thật, không có nơi nào bịa.' },
    { id: 'home-themes', target: 'themes', pose: 'love', say: 'Chọn một chủ đề để xem gợi ý, thả tim để lưu.' },
    { id: 'home-trending', target: 'trending', pose: 'wow', say: 'Những nơi đang được nhắc nhiều tuần này.' },
    { id: 'home-calendar', target: 'calendar', pose: 'point', say: 'Ngày đi của chuyến sẽ được đánh dấu ở đây.' },
    { id: 'home-who', target: 'who', pose: 'wink', say: 'Hồ sơ, thông báo và chat bạn bè ở đây.', guestSay: `Hồ sơ và thông báo cần tài khoản. ${INVITE}` },
  ],
}

const SIDE: Chapter = {
  id: 'side', title: 'Thanh bên', route: '/app',
  steps: [
    { id: 'side-trips', route: '/app/trips', target: 'page-head', pose: 'point', say: 'Chuyến của tôi: mọi chuyến bạn đã lập.', guestSay: `Chuyến của khách chỉ giữ 24 giờ. ${INVITE}` },
    { id: 'side-saved', route: '/app/saved', target: 'page-head', pose: 'love', say: 'Đã lưu: nơi và chủ đề bạn đã thả tim.' },
    { id: 'side-recent', route: '/app/recent', target: 'page-head', pose: 'wink', say: 'Đã xem gần đây: khỏi phải tìm lại.' },
    { id: 'side-settings', route: '/app/profile', target: 'page-head', pose: 'point', say: 'Cài đặt: hồ sơ, thông báo, Google Calendar. Xem lại hướng dẫn cũng ở đây.', guestSay: `Cài đặt cần tài khoản. ${INVITE}` },
    { id: 'side-support', route: '/app/support', target: 'page-head', pose: 'happy', say: 'Hỗ trợ: câu hỏi thường gặp.' },
  ],
}

// Stands in for the real screens of the trip (the guided walk through Tìm hiểu → Đánh giá comes with the sample trip).
const FLOW: Chapter = {
  id: 'flow', title: 'Một chuyến đi', route: '/app',
  steps: [
    { id: 'flow-1', pose: 'curious', say: 'Bước 1 · Tìm hiểu: bạn kể chuyến đi, mình hỏi thêm.' },
    { id: 'flow-2', pose: 'wow', say: 'Bước 2 · Lựa chọn: xem từng nơi rồi tự chọn.' },
    { id: 'flow-3', pose: 'happy', say: 'Bước 3 · Lịch trình: mình xếp lịch, bạn chỉnh tùy ý.' },
    { id: 'flow-4', pose: 'bow', say: 'Bước 4 · Đánh giá: cho mình biết gợi ý có đúng gu không.' },
  ],
}

const FINALE: Chapter = {
  id: 'finale', title: 'Xong', route: '/app',
  steps: [
    { id: 'end', pose: 'cheer', cta: 'done', say: 'Xong một vòng rồi! Thử lập chuyến đầu tiên nhé?' },
    { id: 'start', target: 'new-trip', pose: 'point', cta: 'create', say: 'Bấm đây là mình bắt đầu ngay!' },
  ],
}

// The tour starts on the home page. `kind` only changes the words for what a guest cannot use (Step.guestSay).
export const chapters = (): Chapter[] => [HOME, SIDE, FLOW, FINALE]

export type Flat = { step: Step; chapter: number; route: string | null }
export const flatten = (chapters: Chapter[]): Flat[] => chapters.flatMap((c, i) => c.steps.map((step) => ({ step, chapter: i, route: step.route ?? c.route })))
