"""Logo generator — combines icons, text, and shapes into product logos."""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from logo_creator.icons import get_icon_svg


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _darken(hex_color: str, factor: float = 0.7) -> tuple[int, int, int]:
    """Darken a hex color."""
    r, g, b = _hex_to_rgb(hex_color)
    return (int(r * factor), int(g * factor), int(b * factor))


def _lighten(hex_color: str, factor: float = 0.3) -> tuple[int, int, int]:
    """Lighten a hex color toward white."""
    r, g, b = _hex_to_rgb(hex_color)
    return (
        int(r + (255 - r) * factor),
        int(g + (255 - g) * factor),
        int(b + (255 - b) * factor),
    )


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font, falling back to default if unavailable."""
    font_names = [
        "Inter-Bold.ttf" if bold else "Inter-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    ]
    font_dirs = [
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts"),
        Path.home() / ".local" / "share" / "fonts",
        Path("/System/Library/Fonts"),
    ]

    for font_dir in font_dirs:
        for font_name in font_names:
            for font_path in font_dir.rglob(font_name):
                try:
                    return ImageFont.truetype(str(font_path), size)
                except OSError:
                    continue

    return ImageFont.load_default(size=size)


def _render_svg_to_image(svg_str: str, size: int) -> Image.Image:
    """Render an SVG string to a PIL Image at the given size."""
    png_bytes = cairosvg.svg2png(
        bytestring=svg_str.encode("utf-8"),
        output_width=size,
        output_height=size,
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners to an image."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def generate_icon_badge(
    icon_name: str,
    color: str,
    size: int = 512,
    corner_radius_ratio: float = 0.22,
    icon_padding_ratio: float = 0.25,
    accent: str | None = None,
) -> Image.Image:
    """Generate an icon badge — colored rounded square with white icon.

    Style: App-icon style (like iOS/Android app icons).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background with gradient effect (top lighter, bottom darker)
    radius = int(size * corner_radius_ratio)
    bg_color = _hex_to_rgb(color)
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=bg_color,
    )

    # Subtle gradient overlay — lighter at top
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(size // 3):
        alpha = int(40 * (1 - y / (size // 3)))
        overlay_draw.line([(0, y), (size, y)], fill=(255, 255, 255, alpha))
    img = Image.alpha_composite(img, overlay)

    # Icon (white, centered, with padding)
    icon_size = int(size * (1 - 2 * icon_padding_ratio))
    svg_str = get_icon_svg(icon_name, "#FFFFFF")
    icon_img = _render_svg_to_image(svg_str, icon_size)

    offset = (size - icon_size) // 2
    img.paste(icon_img, (offset, offset), icon_img)

    # Apply rounded corners
    img = _round_corners(img, radius)

    return img


def generate_monogram(
    text: str,
    color: str,
    size: int = 512,
    corner_radius_ratio: float = 0.22,
    accent: str | None = None,
) -> Image.Image:
    """Generate a monogram logo — 1-3 letter abbreviation in a colored badge.

    Style: Clean text-based identity (like Slack, Notion icons).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(size * corner_radius_ratio)
    bg_color = _hex_to_rgb(color)
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=bg_color,
    )

    # Truncate to max 3 chars for monogram
    display_text = text[:3] if len(text) > 3 else text

    # Text — bold, centered
    font_size = int(size * 0.45) if len(display_text) <= 2 else int(size * 0.35)
    font = _load_font(font_size, bold=True)

    bbox = draw.textbbox((0, 0), display_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - bbox[1]  # Adjust for font ascent

    draw.text((x, y), display_text, fill=(255, 255, 255, 255), font=font)

    img = _round_corners(img, radius)
    return img


def generate_full_logo(
    name: str,
    icon_name: str,
    color: str,
    size: int = 512,
    tagline: str = "",
    accent: str | None = None,
    signature: str = "kodeme.io",
) -> Image.Image:
    """Generate a full logo — icon badge + product name + optional tagline.

    Style: Horizontal lockup for headers/splash screens.
    """
    badge_size = size
    text_width = int(size * 3.0)
    total_width = badge_size + int(size * 0.15) + text_width
    total_height = badge_size

    img = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))

    # Icon badge on the left
    badge = generate_icon_badge(icon_name, color, badge_size, accent=accent)
    img.paste(badge, (0, 0), badge)

    draw = ImageDraw.Draw(img)
    text_x = badge_size + int(size * 0.15)

    # Product name
    name_font_size = int(size * 0.28)
    name_font = _load_font(name_font_size, bold=True)
    draw.text(
        (text_x, int(size * 0.18)),
        name,
        fill=_hex_to_rgb(color),
        font=name_font,
    )

    # Tagline
    if tagline:
        tag_font_size = int(size * 0.12)
        tag_font = _load_font(tag_font_size, bold=False)
        draw.text(
            (text_x, int(size * 0.52)),
            tagline,
            fill=(120, 120, 120, 255),
            font=tag_font,
        )

    # Signature
    if signature:
        sig_font_size = int(size * 0.08)
        sig_font = _load_font(sig_font_size, bold=False)
        draw.text(
            (text_x, int(size * 0.72)),
            signature,
            fill=(180, 180, 180, 255),
            font=sig_font,
        )

    return img


def generate_circle_badge(
    icon_name: str,
    color: str,
    size: int = 512,
    icon_padding_ratio: float = 0.28,
    accent: str | None = None,
) -> Image.Image:
    """Generate a circular icon badge.

    Style: Profile picture / avatar style.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Circle background
    bg_color = _hex_to_rgb(color)
    draw.ellipse([(0, 0), (size - 1, size - 1)], fill=bg_color)

    # Subtle lighting
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    center = size // 2
    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < center:
                # Top-left highlight
                highlight = max(0, int(25 * (1 - dist / center) * (1 - y / size)))
                if highlight > 0:
                    overlay_draw.point((x, y), fill=(255, 255, 255, highlight))
    # Skip per-pixel overlay for performance — just do the icon
    img = Image.alpha_composite(img, overlay) if size <= 128 else img

    # Icon
    icon_size = int(size * (1 - 2 * icon_padding_ratio))
    svg_str = get_icon_svg(icon_name, "#FFFFFF")
    icon_img = _render_svg_to_image(svg_str, icon_size)
    offset = (size - icon_size) // 2
    img.paste(icon_img, (offset, offset), icon_img)

    # Circle mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    img.putalpha(mask)

    return img


def generate_favicon(
    icon_name: str,
    color: str,
    accent: str | None = None,
) -> Image.Image:
    """Generate a 32x32 favicon."""
    return generate_icon_badge(icon_name, color, size=32, corner_radius_ratio=0.15, accent=accent)


STYLES: dict[str, Any] = {
    "icon-badge": generate_icon_badge,
    "monogram": generate_monogram,
    "full": generate_full_logo,
    "circle": generate_circle_badge,
    "favicon": generate_favicon,
}
