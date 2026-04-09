"""Recruitment onboarding commands.

Drive the ``recruitment.onboarding`` state machine (submitted → verified →
converted / rejected) from the command line. Useful for bulk approving a
batch of onboarding submissions without clicking through the web UI.

The ``recruitment.onboarding`` model lives in the ``recruitment_management``
private addon. These commands are thin wrappers around its Python actions
(``action_verify``, ``action_convert_to_employee``, ``action_reject``) and
report per-record success/failure so a partial failure does not hide the
successes.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import check_module_installed

app = typer.Typer(help="Recruitment onboarding: verify, convert to employee, reject.")

MODEL = "recruitment.onboarding"


def _require_recruitment(client: object, out: object) -> None:
    """Ensure recruitment_management addon is installed on the target instance."""
    if not check_module_installed(client, "recruitment_management"):
        out.error(  # type: ignore[union-attr]
            "Module 'recruitment_management' is not installed on this instance."
        )
        raise typer.Exit(1)


def _parse_ids(value: str) -> list[int]:
    """Parse a comma-separated list of integer IDs.

    Raises ``typer.BadParameter`` on malformed input. Whitespace around
    commas is tolerated so users can quote "1, 2, 3".
    """
    if not value:
        raise typer.BadParameter("At least one ID is required")
    out: list[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError as exc:
            raise typer.BadParameter(f"Not a valid integer: {chunk!r}") from exc
    if not out:
        raise typer.BadParameter("At least one ID is required")
    return out


def _extract_error(exc: Exception) -> str:
    """Best-effort extraction of a compact one-line error message.

    ``RPCError`` instances from kctl_odoo carry the upstream Odoo error
    object; fall back to ``str(exc)`` for anything else.
    """
    msg = getattr(exc, "message", None) or str(exc)
    # Keep only the first line so the table stays readable.
    return str(msg).splitlines()[0][:140]


# ---------------------------------------------------------------------------
# list / show
# ---------------------------------------------------------------------------


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    state: Annotated[
        str | None,
        typer.Option(
            "--state",
            "-s",
            help="Filter by state: submitted, verified, converted, rejected",
        ),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 200,
) -> None:
    """List onboarding submissions.

    Examples:
        kctl-odoo onboarding list
        kctl-odoo onboarding list --state submitted
        kctl-odoo onboarding list --state verified --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    records = c.search_read(  # type: ignore[attr-defined]
        MODEL,
        domain=domain,
        fields=[
            "id",
            "name",
            "full_legal_name",
            "email",
            "phone",
            "state",
            "employee_id",
            "create_date",
        ],
        limit=limit,
        order="id",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    state_colors = {
        "submitted": "[yellow]submitted[/yellow]",
        "verified": "[cyan]verified[/cyan]",
        "converted": "[green]converted[/green]",
        "rejected": "[red]rejected[/red]",
    }
    for r in records:
        emp = r.get("employee_id")
        emp_label = emp[1] if isinstance(emp, list) else "-"
        state_val = r.get("state") or ""
        rows.append(
            [
                str(r["id"]),
                r.get("name") or "-",
                (r.get("full_legal_name") or "")[:40],
                (r.get("email") or "")[:35],
                r.get("phone") or "-",
                state_colors.get(state_val, state_val),
                emp_label,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "reference": r.get("name"),
                "full_legal_name": r.get("full_legal_name"),
                "email": r.get("email"),
                "phone": r.get("phone"),
                "state": state_val,
                "employee_id": emp[0] if isinstance(emp, list) else None,
                "employee_name": emp[1] if isinstance(emp, list) else None,
                "create_date": r.get("create_date"),
            }
        )

    title = f"Onboarding submissions ({len(records)})"
    if state:
        title += f" [state={state}]"
    out.table(  # type: ignore[union-attr]
        title,
        [
            ("ID", "cyan"),
            ("Ref", "dim"),
            ("Full Legal Name", ""),
            ("Email", "dim"),
            ("Phone", "dim"),
            ("State", ""),
            ("Employee", "green"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def show(
    ctx: typer.Context,
    onboarding_id: Annotated[int, typer.Argument(help="recruitment.onboarding ID")],
) -> None:
    """Show full details for a single onboarding record.

    Examples:
        kctl-odoo onboarding show 42
        kctl-odoo onboarding show 42 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    records = c.read(  # type: ignore[attr-defined]
        MODEL,
        [onboarding_id],
        [
            "id",
            "name",
            "state",
            "full_legal_name",
            "nik",
            "gender",
            "birth_date",
            "birth_place",
            "marital_status",
            "religion",
            "blood_type",
            "email",
            "phone",
            "address_street",
            "address_city",
            "address_province",
            "address_postal_code",
            "bank_name",
            "bank_account_number",
            "bank_account_holder",
            "npwp",
            "ptkp_status",
            "bpjs_kesehatan_number",
            "bpjs_ketenagakerjaan_number",
            "employee_id",
            "applicant_id",
            "create_date",
        ],
    )
    if not records:
        out.error(f"Onboarding record {onboarding_id} not found")  # type: ignore[union-attr]
        raise typer.Exit(1)

    r = records[0]
    emp = r.get("employee_id")
    applicant = r.get("applicant_id")

    def _m2o(val: object) -> str:
        return val[1] if isinstance(val, list) else "-"

    sections = [
        (
            "Identity",
            [
                ("Reference", r.get("name") or "-"),
                ("State", r.get("state") or "-"),
                ("Full Legal Name", r.get("full_legal_name") or "-"),
                ("NIK", r.get("nik") or "-"),
                ("Gender", r.get("gender") or "-"),
                ("Birth", f"{r.get('birth_place') or '?'} / {r.get('birth_date') or '?'}"),
                ("Marital", r.get("marital_status") or "-"),
                ("Religion", r.get("religion") or "-"),
                ("Blood Type", r.get("blood_type") or "-"),
            ],
        ),
        (
            "Contact",
            [
                ("Email", r.get("email") or "-"),
                ("Phone", r.get("phone") or "-"),
                (
                    "Address",
                    ", ".join(
                        p
                        for p in [
                            r.get("address_street"),
                            r.get("address_city"),
                            r.get("address_province"),
                            r.get("address_postal_code"),
                        ]
                        if p
                    )
                    or "-",
                ),
            ],
        ),
        (
            "Tax / Bank",
            [
                ("NPWP", r.get("npwp") or "-"),
                ("PTKP Status", r.get("ptkp_status") or "-"),
                ("BPJS Kesehatan", r.get("bpjs_kesehatan_number") or "-"),
                ("BPJS Ketenagakerjaan", r.get("bpjs_ketenagakerjaan_number") or "-"),
                ("Bank", r.get("bank_name") or "-"),
                ("Account #", r.get("bank_account_number") or "-"),
                ("Account Holder", r.get("bank_account_holder") or "-"),
            ],
        ),
        (
            "Links",
            [
                ("Applicant", _m2o(applicant)),
                ("Created Employee", _m2o(emp)),
                ("Submitted", r.get("create_date") or "-"),
            ],
        ),
    ]
    out.detail(  # type: ignore[union-attr]
        f"Onboarding #{r['id']}",
        sections,
        data_for_json=r,
    )


# ---------------------------------------------------------------------------
# State actions — verify / convert / reject
# ---------------------------------------------------------------------------


def _bulk_action(
    ctx: typer.Context,
    ids: list[int],
    method: str,
    action_label: str,
) -> None:
    """Run an Odoo action on each ID individually and report per-record status.

    The convert_to_employee flow in particular uses ``ensure_one``, so we
    cannot call it on a recordset. Looping here also gives much better
    diagnostics than a single all-or-nothing call.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    rows: list[list[str]] = []
    json_data: list[dict] = []
    ok = 0
    fail = 0
    for rid in ids:
        try:
            c.execute_kw(MODEL, method, [[rid]])  # type: ignore[attr-defined]
        except RPCError as exc:
            msg = _extract_error(exc)
            rows.append([str(rid), "[red]FAIL[/red]", msg])
            json_data.append({"id": rid, "ok": False, "error": msg})
            fail += 1
            continue
        except Exception as exc:  # noqa: BLE001 — surface any error in the table
            msg = _extract_error(exc)
            rows.append([str(rid), "[red]FAIL[/red]", msg])
            json_data.append({"id": rid, "ok": False, "error": msg})
            fail += 1
            continue
        rows.append([str(rid), "[green]OK[/green]", "-"])
        json_data.append({"id": rid, "ok": True, "error": None})
        ok += 1

    out.table(  # type: ignore[union-attr]
        f"{action_label}: {ok} ok / {fail} failed",
        [("ID", "cyan"), ("Status", ""), ("Error", "dim")],
        rows,
        data_for_json=json_data,
    )
    if fail and ok == 0:
        raise typer.Exit(1)


@app.command()
def verify(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Argument(
            help="Comma-separated onboarding IDs (e.g. '1,2,3') or 'all' for every submitted record",
        ),
    ],
) -> None:
    """Mark onboarding submissions as verified.

    Use 'all' to verify every record currently in the 'submitted' state.

    Examples:
        kctl-odoo onboarding verify 1,2,3
        kctl-odoo onboarding verify all
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    if ids.strip().lower() == "all":
        id_list = c.search(MODEL, [("state", "=", "submitted")])  # type: ignore[attr-defined]
        if not id_list:
            out.info("No submitted onboarding records to verify.")  # type: ignore[union-attr]
            return
    else:
        id_list = _parse_ids(ids)

    _bulk_action(ctx, id_list, "action_verify", "Verify")


@app.command()
def convert(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Argument(
            help="Comma-separated onboarding IDs or 'all' for every verified record",
        ),
    ],
) -> None:
    """Convert verified onboarding records into hr.employee records.

    Each record is processed individually so a single bad record does not
    block the rest — per-record status is reported in the output table.

    Examples:
        kctl-odoo onboarding convert 1,2,3
        kctl-odoo onboarding convert all
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    if ids.strip().lower() == "all":
        id_list = c.search(MODEL, [("state", "=", "verified")])  # type: ignore[attr-defined]
        if not id_list:
            out.info("No verified onboarding records to convert.")  # type: ignore[union-attr]
            return
    else:
        id_list = _parse_ids(ids)

    _bulk_action(ctx, id_list, "action_convert_to_employee", "Convert to Employee")


@app.command()
def reject(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Argument(help="Comma-separated onboarding IDs to reject"),
    ],
    reason: Annotated[
        str | None,
        typer.Option("--reason", "-r", help="Rejection reason (written to additional_notes)"),
    ] = None,
) -> None:
    """Reject submitted or verified onboarding records.

    Examples:
        kctl-odoo onboarding reject 7
        kctl-odoo onboarding reject 7,8,9 --reason "Duplicate submission"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_recruitment(c, out)

    id_list = _parse_ids(ids)

    # Optionally stamp the reason on the record before rejecting so it
    # survives as an audit trail. The `additional_notes` field exists on
    # recruitment.onboarding and is free-text.
    if reason:
        try:
            c.write(  # type: ignore[attr-defined]
                MODEL, id_list, {"additional_notes": f"Rejected: {reason}"}
            )
        except RPCError as exc:
            out.warn(f"Could not write rejection reason: {_extract_error(exc)}")  # type: ignore[union-attr]

    _bulk_action(ctx, id_list, "action_reject", "Reject")
