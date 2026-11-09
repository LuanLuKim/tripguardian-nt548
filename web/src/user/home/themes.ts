import type { IconName } from '../ui/icons'

// Ways into a trip on the home page: a theme's prompt becomes the first turn of Tìm hiểu. Photos are real places of
// the corpus (Đồi Đa Phú, Tiệm Cà Phê Cũ 1991, Rừng thông, Hồ Xuân Hương, HongKong Cổ Trấn); they illustrate the
// theme and prove nothing about hours, weather or constraints.
export interface Theme {
  id: string
  ref: string // the tag this theme stands for (docs/PLACE_DECISION.md §20); its subtags are the kinds the user can pick
  title: string
  short: string
  tab: string // the word on the blog's side tab
  subtitle: string
  category: string
  icon: IconName
  photo: string
  alt: string
  prompt: string
  description: string
}

export const THEMES: Theme[] = [
  { id: 'cloud', ref: 'experience:cloud_hunting', tab: 'Săn mây', title: 'Săn mây, đón một ngày mới', short: 'Săn mây buổi sớm', subtitle: 'Theo giờ · Cho những buổi dậy sớm', category: 'Sáng sớm · Thiên nhiên', icon: 'cloud', photo: '/img/home/cloud.jpg', alt: 'Bình minh giữa rừng thông và mây tại Đồi Đa Phú, Đà Lạt', prompt: 'Mình muốn săn mây buổi sáng rồi ngồi cà phê ở Đà Lạt.', description: 'Bắt đầu bằng một buổi sáng giữa núi đồi. Mình sẽ hỏi thời gian đi và cách di chuyển trước khi gợi ý địa điểm cụ thể.' },
  { id: 'cafe', ref: 'category:cafe', tab: 'Cà phê', title: 'Cà phê và một góc bình yên', short: 'Một góc cà phê', subtitle: 'Theo gu · Chậm lại một chút', category: 'Cà phê · Thư thả', icon: 'coffee', photo: '/img/home/cafe.jpg', alt: 'Mặt tiền Tiệm Cà Phê Cũ 1991, Đà Lạt', prompt: 'Mình muốn một chuyến Đà Lạt thư thả, có cà phê và góc ngồi yên tĩnh.', description: 'Một cách mở đầu cho chuyến đi thích ngồi lâu và chuyện trò. Địa điểm và thông tin thực tế được xem ở bước Lựa chọn.' },
  { id: 'pine', ref: 'experience:nature', tab: 'Rừng thông', title: 'Đi một vòng giữa rừng thông', short: 'Giữa rừng thông', subtitle: 'Theo gu · Gần với thiên nhiên', category: 'Thiên nhiên · Đi dạo', icon: 'tree', photo: '/img/home/pine.jpg', alt: 'Rừng thông ở Đà Lạt', prompt: 'Mình thích thiên nhiên và muốn đi dạo giữa rừng thông ở Đà Lạt.', description: 'Thêm một chút thiên nhiên vào chuyến đi. Mình sẽ hỏi khả năng đi bộ của nhóm và mức di chuyển bạn thấy thoải mái.' },
  { id: 'lake', ref: 'experience:sunset_view', tab: 'Bên hồ', title: 'Chiều muộn, hẹn nhau bên hồ', short: 'Một chiều bên hồ', subtitle: 'Theo giờ · Ngắm chiều xuống', category: 'Chiều muộn · Thư giãn', icon: 'sun', photo: '/img/home/lake.jpg', alt: 'Hồ Xuân Hương, Đà Lạt', prompt: 'Mình muốn dành một buổi chiều muộn thư giãn bên hồ ở Đà Lạt.', description: 'Dành một khoảng trống cho buổi chiều. Thời điểm và nơi đến được kiểm tra khi đã có thông tin chuyến đi.' },
  { id: 'rain', ref: 'experience:weather_exposed=sheltered', tab: 'Ngày mưa', title: 'Một ngày mưa vẫn thật vui', short: 'Nếu trời đổ mưa', subtitle: 'Theo thời tiết · Gợi ý trong nhà', category: 'Trong nhà · Ngày mưa', icon: 'home', photo: '/img/home/indoor.jpg', alt: 'Không gian HongKong Cổ Trấn, Đà Lạt', prompt: 'Mình muốn chuẩn bị các chỗ trong nhà cho chuyến Đà Lạt nếu trời mưa.', description: 'Chuẩn bị một lựa chọn trong nhà để chuyến đi linh hoạt hơn. Nơi nào trú mưa được cần có bằng chứng trước khi vào lịch.' },
  { id: 'temple', ref: 'category:religious', tab: 'Chùa, nhà thờ', title: 'Một buổi sáng yên tĩnh, ghé chùa và nhà thờ', short: 'Chùa & nhà thờ', subtitle: 'Theo gu · Chậm và lắng', category: 'Tâm linh · Yên tĩnh', icon: 'moon', photo: '/img/home/temple.jpg', alt: 'Chùa Linh Phước, Đà Lạt', prompt: 'Mình thích những nơi yên tĩnh như chùa và nhà thờ, đi chậm và ngắm kiến trúc ở Đà Lạt.', description: 'Dành cho người thích đi chậm. Mình sẽ hỏi bạn thích kiến trúc, cảnh quan hay chỉ cần một chỗ yên tĩnh, và hỏi cả giờ mở cửa mong muốn.' },
  { id: 'grill', ref: 'category:restaurant', tab: 'Nướng & lẩu', title: 'Tối se lạnh, ăn nướng và lẩu cho ấm bụng', short: 'Nướng & lẩu cho tối lạnh', subtitle: 'Theo gu · Ăn là chính', category: 'Ăn tối · Ấm bụng', icon: 'flame', photo: '/img/home/grill.jpg', alt: 'Mâm đồ nướng ở Tiệm Nướng Màu Vàng, Đà Lạt', prompt: 'Mình muốn ăn đồ nướng và lẩu vào buổi tối se lạnh ở Đà Lạt.', description: 'Bắt đầu từ bữa tối. Mình sẽ hỏi số người, ngân sách và món bạn kiêng trước khi gợi ý quán cụ thể.' },
  { id: 'garden', ref: 'experience:flower_garden', tab: 'Vườn hoa', title: 'Vườn hoa và những góc chụp ảnh đẹp', short: 'Vườn hoa & góc check-in', subtitle: 'Theo gu · Ngắm và chụp ảnh', category: 'Vườn hoa · Chụp ảnh', icon: 'heart', photo: '/img/home/garden.jpg', alt: 'Cổng vòm Vườn hoa Đà Lạt', prompt: 'Mình muốn đi vườn hoa và tìm các góc chụp ảnh đẹp ở Đà Lạt.', description: 'Cho chuyến đi thích ngắm hoa và chụp ảnh. Giờ đẹp và mức đông đúc phụ thuộc vào ngày bạn đi, nên mình sẽ hỏi lịch trước.' },
  { id: 'camp', ref: 'category:camping', tab: 'Cắm trại', title: 'Cắm trại và picnic giữa đồi thông', short: 'Cắm trại, picnic', subtitle: 'Theo gu · Ngoài trời', category: 'Ngoài trời · Cùng nhóm bạn', icon: 'compass', photo: '/img/home/camp.jpg', alt: 'Khu cắm trại Reo Campsite giữa rừng thông, Đà Lạt', prompt: 'Mình muốn cắm trại hoặc picnic giữa đồi thông cùng bạn bè ở Đà Lạt.', description: 'Một chuyến ngoài trời cần chuẩn bị kỹ hơn. Mình sẽ hỏi số người, phương tiện và việc bạn có ngủ lại qua đêm không.' },
  { id: 'falls', ref: 'category:nature', tab: 'Thác', title: 'Thác nước và những trải nghiệm cho người thích vận động', short: 'Thác & trải nghiệm', subtitle: 'Theo gu · Thích vận động', category: 'Thác · Trải nghiệm', icon: 'walk', photo: '/img/home/falls.jpg', alt: 'Thác Datanla, Đà Lạt', prompt: 'Mình thích đi thác và các hoạt động ngoài trời ở Đà Lạt.', description: 'Cho người muốn vận động một chút. Mình sẽ hỏi sức đi bộ của nhóm và thời tiết ngày đi vì đường thác dễ trơn khi mưa.' },
]

export const themeOf = (id: string) => THEMES.find((t) => t.id === id)

const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase()
export const matches = (t: Theme, q: string) => fold(`${t.title} ${t.subtitle} ${t.category}`).includes(fold(q.trim()))
