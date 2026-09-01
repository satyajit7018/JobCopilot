#!/usr/bin/env python3
"""
Generates high-resolution Android PWA PNG and maskable launcher icons for JobCopilot.
"""

from pathlib import Path
from PIL import Image, ImageDraw

def generate_icons():
    icons_dir = Path(__file__).resolve().parent.parent / "frontend" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    sizes = [
        (192, "icon-192.png", False),
        (192, "icon-192-maskable.png", True),
        (512, "icon-512.png", False),
        (512, "icon-512-maskable.png", True),
    ]

    for size, filename, is_maskable in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background rounded rect or full square for maskable
        radius = int(size * 0.22) if not is_maskable else 0
        bg_box = [0, 0, size, size]
        
        # Dark gradient simulation
        for y in range(size):
            factor = y / size
            r = int(11 * (1 - factor) + 6 * factor)
            g = int(15 * (1 - factor) + 8 * factor)
            b = int(25 * (1 - factor) + 13 * factor)
            draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

        # Outer subtle ring
        ring_pad = int(size * 0.08)
        draw.ellipse(
            [ring_pad, ring_pad, size - ring_pad, size - ring_pad],
            outline=(99, 102, 241, 120),
            width=max(2, int(size * 0.015))
        )

        # Ambient central glow circle
        center_glow_pad = int(size * 0.25)
        draw.ellipse(
            [center_glow_pad, center_glow_pad, size - center_glow_pad, size - center_glow_pad],
            fill=(99, 102, 241, 45)
        )

        # Lightning bolt polygon scaled to size
        s = size / 512.0
        # Base coordinates for 512x512
        raw_poly = [
            (280 * s, 70 * s),
            (160 * s, 260 * s),
            (250 * s, 260 * s),
            (220 * s, 440 * s),
            (360 * s, 220 * s),
            (270 * s, 220 * s),
        ]

        # Draw glowing shadow
        shadow_poly = [(x + 2*s, y + 4*s) for x, y in raw_poly]
        draw.polygon(shadow_poly, fill=(6, 182, 212, 100))

        # Main bolt gradient simulation / fill
        draw.polygon(raw_poly, fill=(99, 102, 241, 255), outline=(255, 255, 255, 255))
        
        # Inner cyan highlight
        inner_poly = [
            (276 * s, 85 * s),
            (175 * s, 252 * s),
            (252 * s, 252 * s),
            (230 * s, 390 * s),
            (340 * s, 226 * s),
            (268 * s, 226 * s),
        ]
        draw.polygon(inner_poly, fill=(6, 182, 212, 255))

        out_path = icons_dir / filename
        img.save(out_path, "PNG")
        print(f"✅ Generated {out_path} ({size}x{size})")

if __name__ == "__main__":
    generate_icons()
