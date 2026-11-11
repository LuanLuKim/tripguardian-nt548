import type { IconName } from '../ui/icons'

// Ways into a trip on the home page: a theme's prompt becomes the first turn of Tìm hiểu. The first HOME_THEMES show on the home page; "Xem thêm" opens the rest. Photos are real places of
// the corpus (Đồi Đa Phú, Tiệm Cà Phê Cũ 1991, Rừng thông, Hồ Xuân Hương, HongKong Cổ Trấn); they illustrate the
// theme and prove nothing about hours, weather or constraints.
export interface Theme {
  id: string
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
  { id: 'cloud', tab: 'Săn mây', title: 'Săn mây, đón một ngày mới', short: 'Săn mây buổi sớm', subtitle: 'Theo giờ · Cho những buổi dậy sớm', category: 'Sáng sớm · Thiên nhiên', icon: 'cloud', photo: '/img/home/cloud.jpg', alt: 'Bình minh giữa rừng thông và mây tại Đồi Đa Phú, Đà Lạt', prompt: 'Mình muốn săn mây buổi sáng rồi ngồi cà phê ở Đà Lạt.', description: 'Dậy khi sương còn ngủ trên đồi, chờ nắng đầu ngày vén lớp mây mỏng. Một buổi sáng chậm, đủ để nghe gió và quên đi mọi vội vã.' },
  { id: 'cafe', tab: 'Cà phê', title: 'Cà phê và một góc bình yên', short: 'Một góc cà phê', subtitle: 'Theo gu · Chậm lại một chút', category: 'Cà phê · Thư thả', icon: 'coffee', photo: '/img/home/cafe.jpg', alt: 'Mặt tiền Tiệm Cà Phê Cũ 1991, Đà Lạt', prompt: 'Mình muốn một chuyến Đà Lạt thư thả, có cà phê và góc ngồi yên tĩnh.', description: 'Một góc nhỏ, ly cà phê còn ấm và cả buổi chiều không vội. Dành cho những ai thích ngồi lâu, chuyện trò khẽ và ngắm Đà Lạt trôi qua ô cửa.' },
  { id: 'pine', tab: 'Rừng thông', title: 'Đi một vòng giữa rừng thông', short: 'Giữa rừng thông', subtitle: 'Theo gu · Gần với thiên nhiên', category: 'Thiên nhiên · Đi dạo', icon: 'tree', photo: '/img/home/pine.jpg', alt: 'Rừng thông ở Đà Lạt', prompt: 'Mình thích thiên nhiên và muốn đi dạo giữa rừng thông ở Đà Lạt.', description: 'Đi giữa hai hàng thông, nghe lá chạm nhau và mùi nhựa thơm theo gió. Chỉ cần đôi giày thoải mái và nhịp bước của riêng mình.' },
  { id: 'lake', tab: 'Bên hồ', title: 'Chiều muộn, hẹn nhau bên hồ', short: 'Một chiều bên hồ', subtitle: 'Theo giờ · Ngắm chiều xuống', category: 'Chiều muộn · Thư giãn', icon: 'sun', photo: '/img/home/lake.jpg', alt: 'Hồ Xuân Hương, Đà Lạt', prompt: 'Mình muốn dành một buổi chiều muộn thư giãn bên hồ ở Đà Lạt.', description: 'Chiều xuống chậm bên mặt hồ, nắng cuối ngày tan dần trên mặt nước. Một khoảng lặng để hẹn ai đó, hay chỉ hẹn với chính mình.' },
  { id: 'rain', tab: 'Ngày mưa', title: 'Một ngày mưa vẫn thật vui', short: 'Nếu trời đổ mưa', subtitle: 'Theo thời tiết · Gợi ý trong nhà', category: 'Trong nhà · Ngày mưa', icon: 'home', photo: '/img/home/indoor.jpg', alt: 'Không gian HongKong Cổ Trấn, Đà Lạt', prompt: 'Mình muốn chuẩn bị các chỗ trong nhà cho chuyến Đà Lạt nếu trời mưa.', description: 'Mưa Đà Lạt đến bất chợt, nhưng chuyến đi không vì thế mà dở dang. Vài góc ấm trong nhà, tách trà nóng và tiếng mưa làm nền cho câu chuyện.' },
  { id: 'camp', tab: 'Cắm trại', title: 'Một đêm cắm trại giữa rừng thông', short: 'Cắm trại rừng thông', subtitle: 'Theo gu · Ngủ lại giữa thiên nhiên', category: 'Cắm trại · Thiên nhiên', icon: 'tree', photo: '/img/home/camp.jpg', alt: 'Khu cắm trại dưới tán rừng thông ở Đà Lạt', prompt: 'Mình muốn một đêm cắm trại giữa rừng thông ở Đà Lạt.', description: 'Một đêm ngủ lại giữa rừng thông, sưởi bên lửa và đếm sao trên đầu. Sáng ra, sương đã giăng sẵn trước cửa lều.' },
  { id: 'falls', tab: 'Thác nước', title: 'Nghe tiếng thác giữa núi rừng', short: 'Thác giữa núi rừng', subtitle: 'Theo gu · Đi bộ nhẹ, ngắm nước', category: 'Thác nước · Thiên nhiên', icon: 'rain', photo: '/img/home/falls.jpg', alt: 'Thác nước giữa rừng ở Đà Lạt', prompt: 'Mình muốn đi ngắm thác và đi bộ nhẹ giữa núi rừng Đà Lạt.', description: 'Theo tiếng nước đổ giữa núi rừng, men lối nhỏ phủ rêu xanh. Hơi mát bám vào tóc, còn ồn ào thì ở lại phía sau.' },
  { id: 'garden', tab: 'Vườn hoa', title: 'Dạo giữa vườn hoa và cổng cầu vồng', short: 'Dạo vườn hoa', subtitle: 'Theo gu · Chụp ảnh, đi dạo', category: 'Vườn hoa · Thư thả', icon: 'heart', photo: '/img/home/garden.jpg', alt: 'Cổng hoa ở Vườn hoa thành phố Đà Lạt', prompt: 'Mình muốn dạo vườn hoa và chụp ảnh ở Đà Lạt.', description: 'Dạo giữa muôn sắc hoa và những khung hình không cần chỉnh. Một buổi thong thả cho người thích chụp ảnh và mỉm cười.' },
  { id: 'church', tab: 'Kiến trúc', title: 'Ghé những nơi có kiến trúc đẹp', short: 'Kiến trúc cổ', subtitle: 'Theo gu · Ngắm công trình', category: 'Kiến trúc · Tham quan', icon: 'pin', photo: '/img/home/church.jpg', alt: 'Nhà thờ gạch hồng dưới trời xanh ở Đà Lạt', prompt: 'Mình muốn ghé những công trình kiến trúc đẹp ở Đà Lạt.', description: 'Mái ngói cũ, tường gạch hồng, ô cửa vòm lặng lẽ kể chuyện thời gian. Dành cho người thích đi chậm và ngẩng đầu nhìn.' },
  { id: 'temple', tab: 'Chùa', title: 'Một buổi chiều yên tĩnh ở chùa', short: 'Ghé chùa yên tĩnh', subtitle: 'Theo gu · Chậm lại, tĩnh tâm', category: 'Chùa · Tâm linh', icon: 'compass', photo: '/img/home/temple.jpg', alt: 'Ngôi chùa nhiều tầng dưới trời xanh ở Đà Lạt', prompt: 'Mình muốn ghé một ngôi chùa yên tĩnh ở Đà Lạt.', description: 'Tiếng chuông xa, khói hương mỏng và sân chùa phủ bóng thông. Một điểm dừng yên tĩnh để lòng nhẹ đi giữa chuyến đi.' },
]

export const HOME_THEMES = 5

export const themeOf = (id: string) => THEMES.find((t) => t.id === id)

const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase()
export const matches = (t: Theme, q: string) => fold(`${t.title} ${t.subtitle} ${t.category}`).includes(fold(q.trim()))
