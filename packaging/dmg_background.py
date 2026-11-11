# Regenerate: pip install pillow && python packaging/dmg_background.py packaging   (macOS fonts)
# Draws the DMG window background: 600x400 points; app icon at (160,200), Applications at (440,200).
import sys
from PIL import Image, ImageDraw, ImageFont

W, H, K = 600, 400, 8  # draw at 8x, downscale for smooth edges
img = Image.new("RGB", (W * K, H * K))
d = ImageDraw.Draw(img)
top, bot = (250, 251, 254), (226, 233, 246)
for y in range(H * K):
    t = y / (H * K)
    d.line([(0, y), (W * K, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bot)))

def font(size, weight):
    f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size * K)
    f.set_variation_by_axes([100, min(size, 96), 400, weight])  # width, optical size, grade, weight
    return f

def text(y, s, f, fill):
    w = d.textlength(s, font=f)
    d.text(((W * K - w) / 2, y * K), s, font=f, fill=fill)

text(34, "Office Planner", font(30, 700), (28, 36, 52))
# legend dots in the app's day colours: office, home, holiday, day off
cols = [(29, 76, 156), (31, 107, 41), (163, 40, 26), (138, 97, 0)]
for i, c in enumerate(cols):
    cx, cy, r = (W / 2 - 33 + i * 22) * K, 86 * K, 5 * K
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)

# arrow from app slot to Applications slot
blue, y, x0, x1 = (29, 76, 156), 200 * K, 248 * K, 352 * K
for i in range(5):  # dashed shaft
    a = x0 + i * 18 * K
    d.rounded_rectangle([a, y - 3 * K, a + 10 * K, y + 3 * K], radius=3 * K, fill=blue)
d.polygon([(x1 - 2 * K, y - 15 * K), (x1 + 18 * K, y), (x1 - 2 * K, y + 15 * K)], fill=blue)

text(318, "Drag Office Planner into Applications to install", font(14, 500), (70, 82, 104))

out = sys.argv[1]
img.resize((W * 2, H * 2), Image.LANCZOS).save(f"{out}/dmg-background@2x.png", optimize=True)
img.resize((W, H), Image.LANCZOS).save(f"{out}/dmg-background.png", optimize=True)
