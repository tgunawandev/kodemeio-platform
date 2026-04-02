# Kodemeio Logo Creator

Lightweight CLI tool that generates product logos by combining open-source Lucide icons with colors, text, and shapes.

## Install

```bash
cd tools/logo-creator
uv pip install -e .
```

## Usage

```bash
# List all configured products
logo list

# Create a single logo
logo create sfa                              # Icon badge, 512px
logo create kodemeio --style monogram        # Text monogram
logo create hrm --style full --size 256      # Full lockup with tagline
logo create sfa --style circle               # Circular avatar

# Generate ALL logos for ALL products
logo batch                                   # All styles, all sizes
logo batch --style icon-badge --sizes 128,256
logo batch --products sfa,hrm,kodemeio       # Specific products only

# Preview a product config
logo preview sfa
```

## Styles

| Style | Description | Best For |
|-------|-------------|----------|
| `icon-badge` | Rounded square with icon (app-icon style) | App icons, favicons |
| `monogram` | 1-3 letter text in colored badge | Quick identity, avatars |
| `full` | Icon badge + product name + tagline | Headers, splash screens |
| `circle` | Circular icon badge | Profile pictures, avatars |
| `favicon` | 32x32 icon badge | Browser favicons |

## Products

All products are defined in `products.yaml`. Each has:
- **icon** — Lucide icon name ([browse icons](https://lucide.dev/icons))
- **color** — Primary brand hex color
- **accent** — Secondary color
- **tagline** — Short descriptor

## Adding a New Product

Edit `products.yaml`:

```yaml
products:
  myapp:
    name: "MyApp"
    full_name: "My Application"
    icon: "rocket"          # Any Lucide icon
    color: "#4F46E5"
    accent: "#818CF8"
    tagline: "Launch Fast"
```

Then: `logo create myapp`

## Icon Source

Icons are from [Lucide](https://lucide.dev) — MIT licensed, 1,400+ SVG icons. Icons are fetched on first use and cached at `~/.cache/kodemeio-logo/icons/`.

## Dependencies

- Pillow — image composition
- CairoSVG — SVG to PNG rendering
- httpx — icon fetching
- Typer + Rich — CLI interface
