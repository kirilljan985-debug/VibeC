# -*- coding: utf-8 -*-
"""Генератор иконки VibeC: объёмные буквы «VC» на тёмном фоне.

Слои (снизу вверх): тёмный фон с виньеткой → лёгкое свечение вокруг букв →
тень под буквами → экструзия (3D-глубина вниз) → лицевая грань с радиальным
светом (буквы освещены фронтальным лучом) → световая кромка сверху.

Запуск из корня репозитория:  python tools/make_icon.py
Результат: assets/vibec.ico (+ assets/vibec-preview.png)
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "assets"
FONT = Path(r"C:\Windows\Fonts\ariblk.ttf")  # Arial Black
S = 512          # размер рендера (потом сжимаем в 256)
CENTER = (256, 242)
FONT_SIZE = 296
GLOW_BLUR = 36
GLOW_COLOR = (111, 140, 255)
GLOW_ALPHA = 95
SHADOW_OFFSET = (0, 26)
SHADOW_BLUR = 22
SHADOW_ALPHA = 160
EXTRUDE_DEPTH = 26
CORNER_RADIUS = 92


def text_mask() -> Image.Image:
    """Маска букв «VC» — белое на прозрачном, L-режим."""
    img = Image.new("L", (S, S), 0)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT), FONT_SIZE)
    draw.text(CENTER, "VC", font=font, fill=255, anchor="mm")
    return img


def vertical_gradient(top, bottom) -> Image.Image:
    col = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return col.resize((S, S))


def radial_light(inner, outer, center, radius) -> Image.Image:
    """Радиальный градиент: ярко в центре, темнее к краям — фронтальный луч."""
    img = Image.new("RGB", (S, S))
    px = img.load()
    for y in range(S):
        for x in range(S):
            d = ((x - center[0]) ** 2 + (y - center[1]) ** 2) ** 0.5 / radius
            t = min(d, 1.0)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(inner, outer))
    return img


def build() -> Image.Image:
    mask = text_mask()

    # фон: вертикальный градиент + виньетка (углы темнее)
    bg = vertical_gradient((23, 26, 34), (11, 13, 18))
    vignette = Image.new("L", (S, S), 0)
    ImageDraw.Draw(vignette).ellipse((-S * 0.35, -S * 0.35, S * 1.35, S * 1.35), fill=110)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120)).point(lambda v: 255 - v)
    dark = Image.new("RGB", (S, S), (6, 7, 10))
    bg = Image.composite(bg, dark, vignette)

    icon = bg.convert("RGBA")

    # лёгкое свечение вокруг букв (будто буквы светятся на фон)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow_col = Image.new("RGBA", (S, S), GLOW_COLOR + (0,))
    glow_col.putalpha(mask.point(lambda v: min(v, GLOW_ALPHA)))
    glow = glow_col.filter(ImageFilter.GaussianBlur(GLOW_BLUR))
    icon.alpha_composite(glow)
    # второе, узкое свечение — ореол прямо у кромки
    halo = Image.new("RGBA", (S, S), GLOW_COLOR + (0,))
    halo.putalpha(mask.point(lambda v: min(v, 70)))
    icon.alpha_composite(halo.filter(ImageFilter.GaussianBlur(6)))

    # тень под буквами (смещена вниз, размыта)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh_col = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh_col.putalpha(mask.point(lambda v: SHADOW_ALPHA if v > 40 else 0))
    shadow.alpha_composite(sh_col, SHADOW_OFFSET)
    icon.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))

    # экструзия: глубина вниз, слои темнеют к «дну»
    for i in range(EXTRUDE_DEPTH, 0, -1):
        t = i / EXTRUDE_DEPTH                       # 1 у лицевой грани → 0 внизу
        shade = tuple(round(a * (0.55 + 0.45 * (1 - t))) for a in (58, 68, 108))
        layer = Image.new("RGBA", (S, S), shade + (0,))
        layer.putalpha(mask.point(lambda v: 255 if v > 40 else 0))
        icon.alpha_composite(layer, (0, i))

    # лицевая грань: радиальный свет из центра букв (освещены фронтальным лучом)
    face_img = radial_light((214, 224, 255), (92, 116, 205), (256, 200), 330)
    face = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    face.paste(face_img, (0, 0), mask)
    icon.alpha_composite(face)

    # световая кромка сверху: маска минус её сдвиг вниз = верхние 4 пикселя букв
    from PIL import ImageChops
    shifted = Image.new("L", (S, S), 0)
    shifted.paste(mask, (0, 4))
    rim = ImageChops.subtract(shifted, mask)
    rim_col = Image.new("RGBA", (S, S), (240, 245, 255, 0))
    rim_col.putalpha(rim.point(lambda v: min(v * 2, 210)))
    icon.alpha_composite(rim_col)

    # скруглённые углы
    rounded = Image.new("L", (S, S), 0)
    ImageDraw.Draw(rounded).rounded_rectangle((0, 0, S - 1, S - 1), CORNER_RADIUS, fill=255)
    result = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    result.paste(icon, (0, 0), rounded)
    return result.resize((256, 256), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    icon = build()
    ico_path = OUT / "vibec.ico"
    icon.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                               (64, 64), (128, 128), (256, 256)])
    icon.save(OUT / "vibec-preview.png")
    print(f"OK: {ico_path}")


if __name__ == "__main__":
    sys.exit(main())
