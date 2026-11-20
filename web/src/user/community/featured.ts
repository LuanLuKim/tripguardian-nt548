// The one post TripGuardian pins above the others: what "Khám phá 3D" is and which places have a model. Written by hand (not from the corpus
// like the other editorial posts), so it lives here and not in /data/posts.json. Its gallery blocks show only the places whose model the
// server really serves (/space3d/index.json), so the post never lists a model that is not there.
import type { Post } from './data'

const P = '/space3d/posters/'
const id = {
  hoxuanhuong: '0x31711321284ed77f:0x7752634a02e162e9', quangtruonglam: '0x31711324a3fe0629:0x66eb8ed37afe5989', chodalat: '0x3171130043681211:0x469130bf3ec1f647',
  gadalat: '0x3171125459c2ad83:0xf6e0aaec62936ffb', hotuyenlam: '0x31716b4c43ac569b:0x815f9db8b832aadc', conga: '0x3171133190ba653b:0x3827e1006a34cc4a',
  thanhtam: '0x31711332f4b06465:0x7dda4f11c97145b1', camly: '0x31716cd3e112cd97:0x93fee45aa30cad50', linhphuoc: '0x3171131bc5c884db:0x208932023afedf1b',
  chuatau: '0x3171135a5970f159:0x2144017ae9e29e77', linhan: '0x317141ffe4f39ef7:0x2f6cf0ab0e804624', truclam: '0x31711538a4b67a91:0x14b54d4f0e86e557',
  linhson: '0x317112d7ca5e07f1:0x23d4abb0941400c1', caudat: '0x3171174abf405701:0x4056ac32d7fdab2f', eurogarden: '0x3171173e2cd837c9:0x3794b1a3f09509f4',
  langnam: '0x31716deca1c796bb:0x7f27346736909b08', langfarm: '0x31716dfd71ac9451:0x5f0050e63fe2e31e', dapa: '0x31711310e1f0938f:0xd1fc8c4ad4ee6c1b',
  captreo: '0x31711347082ec713:0xbc862021c38b4507',
}

export const FEATURED_ID = 'tg-3d-intro'
export const FEATURED_COVERS = [`${P}hoxuanhuong.webp`, `${P}linhphuoc.webp`, `${P}gadalat.webp`]

export const FEATURED: Post = {
  id: FEATURED_ID, placeId: id.hoxuanhuong, editorial: true, featured: true, author: 'TripGuardian', at: Date.parse('2026-11-16T08:00:00+07:00'), vis: 'public',
  title: 'Đi một vòng Đà Lạt trước khi đến: hơn 100 nơi đã có mô hình 3D',
  tags: ['khám phá 3d', 'mô hình 3d', 'ý tưởng chuyến đi'],
  facts: {}, reacts: {}, comments: [],
  blocks: [
    { t: 'p', text: 'Chọn nơi qua ảnh và đánh giá thì dễ. Hình dung mình sẽ bước qua cổng nào, đi theo lối nào, ngồi ở đâu và nhìn ra cái gì thì khó hơn nhiều. **Khám phá 3D** là cách TripGuardian giúp bạn đi thử một vòng, ngay trên máy, trước khi đặt chân tới.' },
    { t: 'img', src: `${P}hoxuanhuong.webp`, cap: 'Hồ Xuân Hương nhìn từ mô hình 3D' },
    { t: 'h', text: 'Mô hình 3D là gì?' },
    { t: 'p', text: 'Mỗi mô hình là một cảnh thu nhỏ của chính nơi đó: mặt nước, lối đi, tường rào, mái nhà, cây cối. Bạn kéo chuột để xoay và phóng to như cầm một mô hình trên tay. Muốn đi dạo, hãy để mô hình dẫn bạn một vòng ở tầm mắt người đi bộ: qua cổng, theo lối đi, vào tận trong nhà qua cửa, từ điểm này sang điểm kế.' },
    { t: 'q', text: 'Đi thử trong mô hình một lần, rồi mới quyết định nơi này có đáng xếp vào lịch hay không.' },
    { t: 'h', text: 'Mở bằng cách nào?' },
    { t: 'p', text: 'Mở trang của một nơi, chọn tab **Khám phá 3D**. Tab chỉ có ở những nơi đã dựng mô hình. Mô hình mở ra toàn màn hình; nhấn Esc hoặc nút Quay lại để về trang nơi đó. Dùng trên máy tính: điện thoại sẽ có cùng ứng dụng sau.' },
    { t: 'h', text: 'Những nơi đã có mô hình' },
    { t: 'p', text: 'TripGuardian chỉ dựng cho những nơi đặc biệt, đẹp hoặc nổi tiếng của Đà Lạt, không dựng cho chuỗi cửa hàng hay khách sạn. Bấm vào một nơi để mở trang của nó, rồi chọn tab Khám phá 3D.' },
    { t: 'tour', title: 'Hồ, quảng trường, chợ và ga', ids: [id.hoxuanhuong, id.hotuyenlam, id.quangtruonglam, id.chodalat, id.gadalat, id.captreo] },
    { t: 'tour', title: 'Chùa, thiền viện và nhà thờ', ids: [id.linhphuoc, id.chuatau, id.linhan, id.truclam, id.linhson, id.conga, id.thanhtam, id.camly] },
    { t: 'tour', title: 'Đồi, vườn và làng', ids: [id.caudat, id.eurogarden, id.langnam, id.langfarm, id.dapa] },
    { t: 'h', text: 'Dùng nó để lập lịch' },
    { t: 'p', text: 'Xem xong nơi nào ưng, thêm nó vào chuyến như bình thường. Mô hình chỉ giúp bạn hình dung, không tự thêm gì vào lịch của bạn.' },
    { t: 'p', text: '*Lưu ý:* mô hình dựng từ ảnh, video và vị trí thật của nơi đó; chỗ nào thiếu dữ liệu thì được vẽ thêm cho liền mạch, nên đây là bản tham khảo, không phải bằng chứng. Giờ mở cửa, giá, mức đông và tình trạng đường vẫn lấy từ dữ liệu và đánh giá thật ở trang của nơi đó.' },
  ],
}
