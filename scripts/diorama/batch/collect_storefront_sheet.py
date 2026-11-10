"""Ghép lại contact sheet từ một lượt bridge đã chụp xong, không gửi yêu cầu mới."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

from PIL import Image, ImageDraw, ImageFont

root = DATA
tag, slug = sys.argv[1:]
source = root / 'bridge' / 'out' / tag
if not (source / 'DONE').exists():
    raise SystemExit('Bridge chưa hoàn tất: ' + tag)
pngs = sorted(source.glob('*.png'))
sheet = Image.new('RGB', (1560, 315 * ((len(pngs) + 2) // 3)), 'white')
draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=15)
for i, path in enumerate(pngs):
    x, y = i % 3 * 520, i // 3 * 315
    sheet.paste(Image.open(path).convert('RGB').resize((516, 289)), (x + 2, y + 2))
    draw.text((x + 4, y + 293), path.stem, fill='black', font=font)
destination = root / ('out_' + slug) / ('sheet_' + tag + '.jpg')
sheet.save(destination, quality=85)
print(destination)
