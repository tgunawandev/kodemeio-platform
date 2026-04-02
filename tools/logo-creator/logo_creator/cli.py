"""CLI interface for Kodemeio Logo Creator."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from logo_creator import __version__
from logo_creator.generator import (
    STYLES,
    generate_circle_badge,
    generate_favicon,
    generate_full_logo,
    generate_icon_badge,
    generate_monogram,
)
from logo_creator.icons import get_icon_path

app = typer.Typer(
    name="logo",
    help="Kodemeio Logo Creator — generate product logos from open-source icons.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

PRODUCTS_FILE = Path(__file__).parent.parent / "products.yaml"


def _load_products() -> dict:
    """Load products.yaml configuration."""
    if not PRODUCTS_FILE.exists():
        console.print(f"[red]Products file not found: {PRODUCTS_FILE}[/red]")
        raise typer.Exit(1)
    with open(PRODUCTS_FILE) as f:
        return yaml.safe_load(f)


def _ensure_output_dir(output: Path) -> Path:
    """Ensure output directory exists."""
    output.mkdir(parents=True, exist_ok=True)
    return output


@app.command("create")
def create(
    product: Annotated[str, typer.Argument(help="Product key from products.yaml (e.g., sfa, kodemeio)")],
    style: Annotated[str, typer.Option("--style", "-s", help="Logo style")] = "icon-badge",
    size: Annotated[int, typer.Option("--size", help="Output size in pixels")] = 512,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path("output"),
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: png or svg")] = "png",
) -> None:
    """Create a logo for a single product.

    Examples:
        logo create sfa
        logo create kodemeio --style monogram --size 256
        logo create hrm --style full --output ./logos
        logo create sfa --style circle
    """
    config = _load_products()
    products = config.get("products", {})
    defaults = config.get("defaults", {})

    if product not in products:
        console.print(f"[red]Unknown product '{product}'. Available: {', '.join(sorted(products.keys()))}[/red]")
        raise typer.Exit(1)

    if style not in STYLES:
        console.print(f"[red]Unknown style '{style}'. Available: {', '.join(STYLES.keys())}[/red]")
        raise typer.Exit(1)

    p = products[product]
    _ensure_output_dir(output)

    console.print(f"[bold]Creating {style} logo for {p['name']}...[/bold]")

    # Fetch icon first
    icon_name = p.get("icon", "circle")
    console.print(f"  Icon: [cyan]{icon_name}[/cyan] (Lucide)")
    get_icon_path(icon_name)  # Pre-fetch and cache

    # Generate based on style
    if style == "icon-badge":
        img = generate_icon_badge(
            icon_name=icon_name,
            color=p["color"],
            size=size,
            corner_radius_ratio=defaults.get("corner_radius_ratio", 0.22),
            icon_padding_ratio=defaults.get("icon_padding_ratio", 0.25),
            accent=p.get("accent"),
        )
    elif style == "monogram":
        img = generate_monogram(
            text=p["name"],
            color=p["color"],
            size=size,
            accent=p.get("accent"),
        )
    elif style == "full":
        img = generate_full_logo(
            name=p.get("full_name", p["name"]),
            icon_name=icon_name,
            color=p["color"],
            size=size,
            tagline=p.get("tagline", ""),
            accent=p.get("accent"),
            signature=defaults.get("signature", "kodeme.io"),
        )
    elif style == "circle":
        img = generate_circle_badge(
            icon_name=icon_name,
            color=p["color"],
            size=size,
            accent=p.get("accent"),
        )
    elif style == "favicon":
        img = generate_favicon(icon_name=icon_name, color=p["color"], accent=p.get("accent"))
        size = 32
    else:
        console.print(f"[red]Style '{style}' not implemented.[/red]")
        raise typer.Exit(1)

    filename = f"{product}-{style}-{size}.{fmt}"
    filepath = output / filename

    if fmt == "png":
        img.save(filepath, "PNG", optimize=True)
    elif fmt == "svg":
        # For SVG output, generate the badge as SVG directly
        console.print("[yellow]SVG output generates PNG (SVG composition not yet supported).[/yellow]")
        img.save(filepath.with_suffix(".png"), "PNG", optimize=True)
        filepath = filepath.with_suffix(".png")
    else:
        img.save(filepath, "PNG", optimize=True)

    console.print(f"  [green]Saved: {filepath}[/green] ({img.size[0]}x{img.size[1]})")


@app.command("batch")
def batch(
    style: Annotated[str, typer.Option("--style", "-s", help="Logo style (or 'all' for all styles)")] = "all",
    sizes: Annotated[str, typer.Option("--sizes", help="Comma-separated sizes")] = "64,128,256,512",
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path("output"),
    products_filter: Annotated[
        str | None, typer.Option("--products", "-p", help="Comma-separated product keys")
    ] = None,
) -> None:
    """Generate logos for ALL products in products.yaml.

    Examples:
        logo batch
        logo batch --style icon-badge --sizes 128,256
        logo batch --products sfa,hrm,kodemeio
        logo batch --style all --output ./brand-assets
    """
    config = _load_products()
    products = config.get("products", {})
    defaults = config.get("defaults", {})
    size_list = [int(s.strip()) for s in sizes.split(",")]

    if products_filter:
        keys = [k.strip() for k in products_filter.split(",")]
        products = {k: v for k, v in products.items() if k in keys}

    styles_to_run = list(STYLES.keys()) if style == "all" else [style]

    total = len(products) * len(styles_to_run) * len(size_list)
    console.print(f"[bold]Generating {total} logos for {len(products)} products...[/bold]")

    generated = 0
    for product_key, p in sorted(products.items()):
        product_dir = _ensure_output_dir(output / product_key)
        icon_name = p.get("icon", "circle")

        # Pre-fetch icon
        try:
            get_icon_path(icon_name)
        except FileNotFoundError:
            console.print(f"  [yellow]Skipping {product_key}: icon '{icon_name}' not found[/yellow]")
            continue

        for s in styles_to_run:
            for sz in size_list:
                # Skip unreasonable combinations
                if s == "favicon" and sz != 32:
                    continue
                if s == "full" and sz < 128:
                    continue

                actual_size = 32 if s == "favicon" else sz

                try:
                    if s == "icon-badge":
                        img = generate_icon_badge(icon_name, p["color"], actual_size, accent=p.get("accent"))
                    elif s == "monogram":
                        img = generate_monogram(p["name"], p["color"], actual_size, accent=p.get("accent"))
                    elif s == "full":
                        img = generate_full_logo(
                            p.get("full_name", p["name"]),
                            icon_name,
                            p["color"],
                            actual_size,
                            tagline=p.get("tagline", ""),
                            accent=p.get("accent"),
                            signature=defaults.get("signature", "kodeme.io"),
                        )
                    elif s == "circle":
                        img = generate_circle_badge(icon_name, p["color"], actual_size, accent=p.get("accent"))
                    elif s == "favicon":
                        img = generate_favicon(icon_name, p["color"], accent=p.get("accent"))
                    else:
                        continue

                    filename = f"{product_key}-{s}-{actual_size}.png"
                    img.save(product_dir / filename, "PNG", optimize=True)
                    generated += 1
                except Exception as e:
                    console.print(f"  [red]Error: {product_key}/{s}/{sz}: {e}[/red]")

    console.print(f"\n[green bold]Done! Generated {generated} logos in {output}/[/green bold]")


@app.command("list")
def list_products() -> None:
    """List all configured products and their icons/colors."""
    config = _load_products()
    products = config.get("products", {})

    table = Table(title="Kodemeio Products", show_lines=False)
    table.add_column("Key", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Icon", style="green")
    table.add_column("Color")
    table.add_column("Tagline", style="dim")

    for key in sorted(products.keys()):
        p = products[key]
        color_block = f"[on {p['color']}]  [/on {p['color']}] {p['color']}"
        table.add_row(key, p["name"], p.get("icon", "—"), color_block, p.get("tagline", ""))

    console.print(table)
    console.print(f"\n[dim]{len(products)} products configured. Styles: {', '.join(STYLES.keys())}[/dim]")


@app.command("preview")
def preview(
    product: Annotated[str, typer.Argument(help="Product key")],
) -> None:
    """Preview a product's config and available icon."""
    config = _load_products()
    products = config.get("products", {})

    if product not in products:
        console.print(f"[red]Unknown product '{product}'.[/red]")
        raise typer.Exit(1)

    p = products[product]
    console.print(f"\n[bold]{p.get('full_name', p['name'])}[/bold] ({product})")
    console.print(f"  Icon:    [cyan]{p.get('icon', 'none')}[/cyan] (Lucide)")
    console.print(f"  Color:   [on {p['color']}]    [/on {p['color']}] {p['color']}")
    if p.get("accent"):
        console.print(f"  Accent:  [on {p['accent']}]    [/on {p['accent']}] {p['accent']}")
    if p.get("tagline"):
        console.print(f"  Tagline: {p['tagline']}")

    # Check icon availability
    try:
        icon_path = get_icon_path(p.get("icon", "circle"))
        console.print(f"  Status:  [green]Icon cached at {icon_path}[/green]")
    except FileNotFoundError:
        console.print("  Status:  [red]Icon not found on Lucide CDN[/red]")

    console.print(f"\n  Available styles: {', '.join(STYLES.keys())}")
    console.print(f"  Generate: [dim]logo create {product} --style icon-badge --size 256[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version")] = False,
) -> None:
    """Kodemeio Logo Creator — generate product logos from open-source icons."""
    if version:
        console.print(f"kodemeio-logo {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


def app_run() -> None:
    """Entry point."""
    app()
