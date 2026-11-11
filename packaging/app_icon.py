# Regenerate: pip install pillow && python packaging/app_icon.py
# Writes packaging/icon.icns (macOS), packaging/icon.ico (Windows) and
# office_planner/gui/icon.png (Linux .deb + the Tk window icon).
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S, K = 1024, 4  # final size, supersampling


def rr(d, box, r, fill):
    d.rounded_rectangle([v * K for v in box], radius=r * K, fill=fill)


def draw() -> Image.Image:
    size = S * K
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # soft drop shadow under the tile
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rr(ImageDraw.Draw(shadow), (100, 120, 924, 944), 185, (0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18 * K)))

    # tile: vertical blue gradient, macOS-style 824px rounded square
    grad = Image.new("RGBA", img.size)
    gd = ImageDraw.Draw(grad)
    top, bot = (74, 128, 235), (29, 76, 156)
    for y in range(size):
        t = y / size
        gd.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bot)))
    mask = Image.new("L", img.size, 0)
    rr(ImageDraw.Draw(mask), (100, 100, 924, 924), 185, 255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # calendar card with a red header and two binder rings
    rr(d, (232, 262, 792, 800), 64, (255, 255, 255))
    rr(d, (232, 262, 792, 400), 64, (229, 83, 61))
    d.rectangle([232 * K, 340 * K, 792 * K, 400 * K], fill=(229, 83, 61))
    for x in (362, 662):
        rr(d, (x - 22, 222, x + 22, 318), 22, (240, 243, 250))

    # Mon-Fri x 3 weeks in the app's day colours: office, home, day off
    o, h, f = (59, 111, 216), (47, 158, 68), (240, 180, 0)
    rows = [(o, h, o, h, o), (o, o, h, o, h), (o, h, o, f, f)]
    cell, gap, left, top_y = 82, 18, 287, 450
    for r, row in enumerate(rows):
        for c, col in enumerate(row):
            x0, y0 = left + c * (cell + gap), top_y + r * (cell + gap)
            rr(d, (x0, y0, x0 + cell, y0 + cell), 18, col)
    return img.resize((S, S), Image.LANCZOS)


if __name__ == "__main__":
    icon = draw()
    icon.save(ROOT / "packaging" / "icon.icns",
              sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    icon.save(ROOT / "packaging" / "icon.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.resize((256, 256), Image.LANCZOS).save(ROOT / "office_planner" / "gui" / "icon.png",
                                                optimize=True)
