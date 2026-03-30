"""Manage IR sequences (auto-numbering)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Manage IR sequences (numbering).")


@app.command("list")
def list_sequences(
    ctx: typer.Context,
    model: Annotated[
        str | None, typer.Option("--model", "-m", help="Filter by code pattern (e.g. sale, account)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of sequences to list")] = 50,
) -> None:
    """List IR sequences.

    Shows all sequences with their prefix, suffix, next number, and padding.

    Examples:
        kctl-odoo sequences list
        kctl-odoo sequences list --model sale
        kctl-odoo sequences list --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        domain.append(("code", "ilike", model))

    sequences = c.search_read(
        "ir.sequence",
        domain=domain,
        fields=["name", "code", "prefix", "suffix", "number_next", "padding"],
        limit=limit,
        order="name",
    )

    if not sequences:
        out.info(f"No sequences found{' matching ' + model if model else ''}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for seq in sequences:
        rows.append(
            [
                seq.get("name", ""),
                seq.get("code", "") or "",
                seq.get("prefix", "") or "",
                seq.get("suffix", "") or "",
                str(seq.get("number_next", "")),
                str(seq.get("padding", "")),
            ]
        )

    out.table(
        f"IR Sequences ({len(sequences)} found)",
        [("Name", ""), ("Code", "cyan"), ("Prefix", ""), ("Suffix", ""), ("Next #", "green"), ("Padding", "dim")],
        rows,
        data_for_json=sequences,
    )

    if actx.json_mode:
        out.raw_json(sequences)


@app.command("get")
def get(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Sequence code to look up (e.g. sale.order)")],
) -> None:
    """Get detailed info for a sequence by code.

    Examples:
        kctl-odoo sequences get sale.order
        kctl-odoo sequences get account.move
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sequences = c.search_read(
        "ir.sequence",
        domain=[("code", "=", code)],
        fields=[
            "name",
            "code",
            "prefix",
            "suffix",
            "number_next",
            "number_increment",
            "padding",
            "active",
            "company_id",
            "implementation",
        ],
        limit=5,
    )

    if not sequences:
        out.error(f"No sequence found with code '{code}'.")
        raise typer.Exit(1)

    for seq in sequences:
        company = seq.get("company_id")
        company_name = company[1] if isinstance(company, list) else str(company or "global")
        out.info(f"Name:          {seq.get('name')}")
        out.info(f"Code:          {seq.get('code')}")
        out.info(f"Prefix:        {seq.get('prefix', '') or '(none)'}")
        out.info(f"Suffix:        {seq.get('suffix', '') or '(none)'}")
        out.info(f"Next Number:   {seq.get('number_next')}")
        out.info(f"Increment:     {seq.get('number_increment')}")
        out.info(f"Padding:       {seq.get('padding')}")
        out.info(f"Active:        {seq.get('active')}")
        out.info(f"Company:       {company_name}")
        out.info(f"Implementation: {seq.get('implementation', 'standard')}")
        if len(sequences) > 1:
            out.info("---")

    if actx.json_mode:
        out.raw_json(sequences if len(sequences) > 1 else sequences[0])


@app.command("reset")
def reset(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Sequence code to reset (e.g. sale.order)")],
    number: Annotated[int, typer.Option("--number", "-n", help="New next number to set")] = ...,
    force: Annotated[bool, typer.Option("--force", help="Required: confirm you want to reset the counter")] = False,
) -> None:
    """Reset a sequence counter to a specific number.

    Requires --force to prevent accidental resets.
    Sets number_next_actual on the sequence record.

    Examples:
        kctl-odoo sequences reset sale.order --number 1000 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force:
        out.error("This operation requires --force to confirm you want to reset the sequence counter.")
        raise typer.Exit(1)

    sequences = c.search_read(
        "ir.sequence",
        domain=[("code", "=", code)],
        fields=["id", "name", "code", "number_next"],
        limit=1,
    )

    if not sequences:
        out.error(f"No sequence found with code '{code}'.")
        raise typer.Exit(1)

    seq = sequences[0]
    old_number = seq.get("number_next")

    try:
        c.execute_kw("ir.sequence", "write", [[seq["id"]], {"number_next_actual": number}])
        out.success(f"Sequence '{seq['name']}' ({code}) reset: {old_number} -> {number}.")
    except Exception as e:
        out.error(f"Failed to reset sequence '{code}': {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json(
            {
                "id": seq["id"],
                "code": code,
                "name": seq["name"],
                "old_number": old_number,
                "new_number": number,
            }
        )


@app.command("preview")
def preview(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Sequence code to preview (e.g. sale.order)")],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of preview entries to generate")] = 5,
) -> None:
    """Preview next N sequence numbers without consuming them.

    Reads the current number_next, prefix, suffix, and padding to generate
    preview strings showing what the next numbers would look like.

    Examples:
        kctl-odoo sequences preview sale.order
        kctl-odoo sequences preview account.move --count 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sequences = c.search_read(
        "ir.sequence",
        domain=[("code", "=", code)],
        fields=["name", "code", "prefix", "suffix", "number_next", "padding"],
        limit=1,
    )

    if not sequences:
        out.error(f"No sequence found with code '{code}'.")
        raise typer.Exit(1)

    seq = sequences[0]
    prefix = seq.get("prefix") or ""
    suffix = seq.get("suffix") or ""
    number_next = seq.get("number_next", 1)
    padding = seq.get("padding", 5)

    # Generate preview strings (without consuming)
    previews = []
    for i in range(count):
        num_str = str(number_next + i).zfill(padding)
        formatted = f"{prefix}{num_str}{suffix}"
        previews.append(formatted)

    out.info(f"Sequence: {seq['name']} (code: {code})")
    out.info(f"Pattern:  {prefix}{'#' * padding}{suffix}")
    out.info("")
    out.info(f"Next {count} numbers (preview only — not consumed):")
    for p in previews:
        out.info(f"  {p}")

    if actx.json_mode:
        out.raw_json(
            {
                "code": code,
                "name": seq["name"],
                "prefix": prefix,
                "suffix": suffix,
                "padding": padding,
                "number_next": number_next,
                "previews": previews,
            }
        )
