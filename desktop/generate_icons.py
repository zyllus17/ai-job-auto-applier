#!/usr/bin/env python3
"""Generate high-resolution cross-platform icons for macOS (.icns), Windows (.ico), and Linux/Web (.png)."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("📦 Installing Pillow for icon generation...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def create_master_icon(size=1024):
    # Create image with RGBA
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle badge base
    padding = int(size * 0.08)
    corner_radius = int(size * 0.22)
    box = [padding, padding, size - padding, size - padding]

    # Gradient background simulation
    # Deep indigo to electric violet with cyan rim
    for i in range(padding, size - padding):
        ratio = (i - padding) / (size - 2 * padding)
        # Interpolate color (indigo: 25, 20, 60 -> violet: 90, 40, 180)
        r = int(20 + 80 * ratio)
        g = int(25 + 30 * ratio)
        b = int(65 + 180 * ratio)
        # Draw horizontal slice with rounded mask
        draw.line([(padding, i), (size - padding, i)], fill=(r, g, b, 255))

    # Mask with rounded rectangle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(box, radius=corner_radius, fill=255)

    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base.paste(img, (0, 0), mask)

    # Add outer glow / border
    border_draw = ImageDraw.Draw(base)
    border_draw.rounded_rectangle(box, radius=corner_radius, outline=(129, 140, 248, 220), width=int(size * 0.02))

    # Inner emblem: Rocket + Circuit nodes
    center_x, center_y = size // 2, size // 2

    # Glowing emblem circle in center
    emblem_radius = int(size * 0.28)
    emblem_box = [center_x - emblem_radius, center_y - emblem_radius, center_x + emblem_radius, center_y + emblem_radius]
    
    # Circuit lines
    for angle_offset in [-45, 45, 135, 225]:
        lx = center_x + int(emblem_radius * 1.3 * (1 if angle_offset in [-45, 45] else -1))
        ly = center_y + int(emblem_radius * 1.3 * (1 if angle_offset in [45, 135] else -1))
        border_draw.line([(center_x, center_y), (lx, ly)], fill=(6, 182, 212, 160), width=int(size * 0.015))
        border_draw.ellipse([lx - 12, ly - 12, lx + 12, ly + 12], fill=(6, 182, 212, 255))

    # Rocket triangle / fuselage
    rocket_w = int(size * 0.16)
    rocket_h = int(size * 0.36)
    
    # Rocket body
    points = [
        (center_x, center_y - rocket_h // 2 - int(size * 0.04)),
        (center_x + rocket_w, center_y + rocket_h // 3),
        (center_x + rocket_w // 2, center_y + rocket_h // 2),
        (center_x - rocket_w // 2, center_y + rocket_h // 2),
        (center_x - rocket_w, center_y + rocket_h // 3),
    ]
    border_draw.polygon(points, fill=(255, 255, 255, 245))

    # Rocket window
    win_r = int(size * 0.045)
    border_draw.ellipse([center_x - win_r, center_y - win_r - int(size * 0.05), center_x + win_r, center_y + win_r - int(size * 0.05)], fill=(79, 70, 229, 255), outline=(6, 182, 212, 255), width=int(size * 0.01))

    # Rocket thruster flame
    flame_pts = [
        (center_x - rocket_w // 3, center_y + rocket_h // 2 + 2),
        (center_x, center_y + rocket_h // 2 + int(size * 0.12)),
        (center_x + rocket_w // 3, center_y + rocket_h // 2 + 2),
    ]
    border_draw.polygon(flame_pts, fill=(249, 115, 22, 240))

    inner_flame = [
        (center_x - rocket_w // 6, center_y + rocket_h // 2 + 2),
        (center_x, center_y + rocket_h // 2 + int(size * 0.07)),
        (center_x + rocket_w // 6, center_y + rocket_h // 2 + 2),
    ]
    border_draw.polygon(inner_flame, fill=(251, 191, 36, 255))

    return base

def main():
    print("🎨 Generating Master Icon (1024x1024)...")
    icon1024 = create_master_icon(1024)
    png_path = ASSETS_DIR / "icon.png"
    icon1024.save(png_path, "PNG")
    print(f"✅ Saved master PNG: {png_path}")

    # Generate Linux Freedesktop Icons (assets/icons/{w}x{h}.png)
    print("🐧 Generating Linux Freedesktop icons (16x16 through 1024x1024)...")
    linux_icons_dir = ASSETS_DIR / "icons"
    linux_icons_dir.mkdir(parents=True, exist_ok=True)
    linux_sizes = [16, 24, 32, 48, 64, 128, 256, 512, 1024]
    for sz in linux_sizes:
        resized_icon = icon1024.resize((sz, sz), Image.Resampling.LANCZOS)
        resized_icon.save(linux_icons_dir / f"{sz}x{sz}.png", "PNG")
    print(f"✅ Saved Linux icons to: {linux_icons_dir}")

    # Generate Windows .ico

    print("🪟 Generating Windows icon.ico...")
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    ico_images = [icon1024.resize(s, Image.Resampling.LANCZOS) for s in ico_sizes]
    ico_path = ASSETS_DIR / "icon.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
        append_images=ico_images[1:]
    )
    print(f"✅ Saved Windows ICO: {ico_path}")

    # Generate macOS .icns via iconutil
    if sys.platform == "darwin":
        print("🍎 Generating macOS icon.icns via iconutil...")
        iconset_dir = ASSETS_DIR / "icon.iconset"
        if iconset_dir.exists():
            shutil.rmtree(iconset_dir)
        iconset_dir.mkdir(parents=True)

        sizes_map = {
            "icon_16x16.png": (16, 16),
            "icon_16x16@2x.png": (32, 32),
            "icon_32x32.png": (32, 32),
            "icon_32x32@2x.png": (64, 64),
            "icon_128x128.png": (128, 128),
            "icon_128x128@2x.png": (256, 256),
            "icon_256x256.png": (256, 256),
            "icon_256x256@2x.png": (512, 512),
            "icon_512x512.png": (512, 512),
            "icon_512x512@2x.png": (1024, 1024),
        }

        for filename, dims in sizes_map.items():
            resized = icon1024.resize(dims, Image.Resampling.LANCZOS)
            resized.save(iconset_dir / filename, "PNG")

        icns_path = ASSETS_DIR / "icon.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)], check=True)
        shutil.rmtree(iconset_dir)
        print(f"✅ Saved macOS ICNS: {icns_path}")

    print("\n🎉 All cross-platform icon assets generated successfully!")

if __name__ == "__main__":
    main()
