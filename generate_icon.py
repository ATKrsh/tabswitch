# generate_icon.py
# Generates a premium .ico for the Assistive Tab Switcher.
# Two visual zones: outer donut (cyan) and inner solid circle (bright cyan).

from PIL import Image, ImageDraw
import base64, os

def create_icon():
    SIZE = 256
    cx, cy = SIZE // 2, SIZE // 2
    OUTER_R = 110
    INNER_CUTOUT_R = 52
    INNER_R = 32

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Outer circle (dark glassmorphic base) ──────────────────────────────
    draw.ellipse(
        [cx - OUTER_R, cy - OUTER_R, cx + OUTER_R, cy + OUTER_R],
        fill=(22, 28, 44, 230)
    )
    # Outer ring border (cyan)
    for w in range(5, 0, -1):
        alpha = int(180 * (w / 5))
        draw.ellipse(
            [cx - OUTER_R + (5 - w), cy - OUTER_R + (5 - w),
             cx + OUTER_R - (5 - w), cy + OUTER_R - (5 - w)],
            outline=(0, 200, 255, alpha), width=1
        )

    # ── Dark separator ring (creates visual "donut") ───────────────────────
    draw.ellipse(
        [cx - INNER_CUTOUT_R - 6, cy - INNER_CUTOUT_R - 6,
         cx + INNER_CUTOUT_R + 6, cy + INNER_CUTOUT_R + 6],
        fill=(8, 12, 22, 255)
    )

    # ── Inner solid circle (bright cyan, Mode 2) ───────────────────────────
    draw.ellipse(
        [cx - INNER_R, cy - INNER_R, cx + INNER_R, cy + INNER_R],
        fill=(0, 180, 240, 255)
    )
    # Inner ring highlight
    for w in range(3, 0, -1):
        alpha = int(220 * (w / 3))
        draw.ellipse(
            [cx - INNER_R + (3 - w), cy - INNER_R + (3 - w),
             cx + INNER_R - (3 - w), cy + INNER_R - (3 - w)],
            outline=(140, 240, 255, alpha), width=1
        )

    # ── Chevron arrows in the donut zone ──────────────────────────────────
    arrow_color = (160, 220, 255, 200)
    mid_r = (INNER_CUTOUT_R + 6 + OUTER_R) // 2
    # Top chevron →
    ax, ay = cx, cy - mid_r
    draw.polygon(
        [(ax - 18, ay - 10), (ax + 6, ay), (ax - 18, ay + 10)],
        fill=arrow_color
    )
    # Bottom chevron ← (flip)
    ax2, ay2 = cx, cy + mid_r
    draw.polygon(
        [(ax2 + 18, ay2 - 10), (ax2 - 6, ay2), (ax2 + 18, ay2 + 10)],
        fill=arrow_color
    )

    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save("icon.ico", sizes=ico_sizes)
    print("icon.ico saved.")

    # Also export base64 for embedding
    raw = open("icon.ico", "rb").read()
    b64 = base64.b64encode(raw).decode()
    print(f"Base64 length: {len(b64)}")
    with open("icon_b64.txt", "w") as f:
        f.write(b64)
    print("icon_b64.txt saved.")

if __name__ == "__main__":
    create_icon()
