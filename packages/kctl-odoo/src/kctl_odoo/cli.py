"""Main CLI entry point for kctl-odoo."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_odoo import __version__
from kctl_odoo.commands.accounting_cmd import app as accounting_app
from kctl_odoo.commands.addons_cmd import app as addons_app
from kctl_odoo.commands.approvals_cmd import app as approvals_app
from kctl_odoo.commands.assets_cmd import app as assets_app
from kctl_odoo.commands.audit_cmd import app as audit_app
from kctl_odoo.commands.auto_maintain_cmd import app as auto_maintain_app
from kctl_odoo.commands.automation_cmd import app as automation_app
from kctl_odoo.commands.backup import app as backup_app
from kctl_odoo.commands.bank_cmd import app as bank_app
from kctl_odoo.commands.budget_cmd import app as budget_app
from kctl_odoo.commands.bundles import app as bundles_app
from kctl_odoo.commands.cleanup import app as cleanup_app
from kctl_odoo.commands.companies import app as companies_app
from kctl_odoo.commands.compliance_cmd import app as compliance_app
from kctl_odoo.commands.config_cmd import app as config_app
from kctl_odoo.commands.config_server import app as config_server_app
from kctl_odoo.commands.configure import app as configure_app
from kctl_odoo.commands.pricelist_cmd import app as pricelist_app
from kctl_odoo.commands.crm_cmd import app as crm_app
from kctl_odoo.commands.cron import app as cron_app
from kctl_odoo.commands.currency_cmd import app as currency_app
from kctl_odoo.commands.dashboard import app as dashboard_app
from kctl_odoo.commands.data_quality_cmd import app as data_quality_app
from kctl_odoo.commands.databases import app as databases_app
from kctl_odoo.commands.delivery_cmd import app as delivery_app
from kctl_odoo.commands.deploy import app as deploy_app
from kctl_odoo.commands.dev import app as dev_app
from kctl_odoo.commands.dev_mode import app as dev_mode_app
from kctl_odoo.commands.diff import app as diff_app
from kctl_odoo.commands.dunning_cmd import app as dunning_app
from kctl_odoo.commands.e2e import app as e2e_app
from kctl_odoo.commands.events_cmd import app as events_app
from kctl_odoo.commands.export_cmd import app as export_app
from kctl_odoo.commands.fastapi_cmd import app as fastapi_app
from kctl_odoo.commands.fleet_cmd import app as fleet_app
from kctl_odoo.commands.forms_cmd import app as forms_app
from kctl_odoo.commands.generate import app as generate_app
from kctl_odoo.commands.helpdesk_cmd import app as helpdesk_app
from kctl_odoo.commands.history_cmd import app as history_app
from kctl_odoo.commands.hr_cmd import app as hr_app
from kctl_odoo.commands.import_cmd import app as import_app
from kctl_odoo.commands.accurate import app as accurate_app
from kctl_odoo.commands.integration import app as integration_app
from kctl_odoo.commands.inventory_cmd import app as inventory_app
from kctl_odoo.commands.jobs import app as jobs_app
from kctl_odoo.commands.kpi_cmd import app as kpi_app
from kctl_odoo.commands.lint import app as lint_app
from kctl_odoo.commands.local import app as local_app
from kctl_odoo.commands.logs import app as logs_app
from kctl_odoo.commands.mail import app as mail_app
from kctl_odoo.commands.maintenance import app as maintenance_app
from kctl_odoo.commands.manifest_cmd import app as manifest_app
from kctl_odoo.commands.migrate import app as migrate_app
from kctl_odoo.commands.mis_reports_cmd import app as mis_reports_app
from kctl_odoo.commands.modules import app as modules_app
from kctl_odoo.commands.monitor_cmd import app as monitor_app
from kctl_odoo.commands.mrp_cmd import app as mrp_app
from kctl_odoo.commands.onboarding_cmd import app as onboarding_app
from kctl_odoo.commands.orm_cmd import app as orm_app
from kctl_odoo.commands.partners import app as partners_app
from kctl_odoo.commands.payment_gateways_cmd import app as payment_gateways_app
from kctl_odoo.commands.performance import app as performance_app
from kctl_odoo.commands.periods_cmd import app as periods_app
from kctl_odoo.commands.pipeline import app as pipeline_app
from kctl_odoo.commands.pos_cmd import app as pos_app
from kctl_odoo.commands.products_cmd import app as products_app
from kctl_odoo.commands.project_cmd import app as project_app
from kctl_odoo.commands.purchasing_cmd import app as purchasing_app
from kctl_odoo.commands.quality_cmd import app as quality_app
from kctl_odoo.commands.record_rules import app as record_rules_app
from kctl_odoo.commands.repl import app as repl_app
from kctl_odoo.commands.report import app as report_app
from kctl_odoo.commands.report_cmd import app as report_template_app
from kctl_odoo.commands.report_custom_query_cmd import app as report_custom_query_app
from kctl_odoo.commands.report_drill_route_cmd import app as report_drill_route_app
from kctl_odoo.commands.report_format_cmd import app as report_format_app
from kctl_odoo.commands.sql_export_cmd import app as sql_export_app
from kctl_odoo.commands.report_formats_cmd import app as report_formats_app
from kctl_odoo.commands.report_subkpi_cmd import app as report_subkpi_app
from kctl_odoo.commands.report_schedule_cmd import app as report_schedule_app
from kctl_odoo.commands.report_type_cmd import app as report_type_app
from kctl_odoo.commands.roles import app as roles_app
from kctl_odoo.commands.sales_cmd import app as sales_app
from kctl_odoo.commands.security import app as security_app
from kctl_odoo.commands.self_test import app as self_test_app
from kctl_odoo.commands.sequences_cmd import app as sequences_app
from kctl_odoo.commands.sessions import app as sessions_app
from kctl_odoo.commands.setup import app as setup_app
from kctl_odoo.commands.shell import app as shell_app
from kctl_odoo.commands.skill_cmd import app as skill_app
from kctl_odoo.commands.staging_cmd import app as staging_app
from kctl_odoo.commands.statements_cmd import app as statements_app
from kctl_odoo.commands.storage import app as storage_app
from kctl_odoo.commands.support_cmd import app as support_app
from kctl_odoo.commands.tax_cmd import app as tax_app
from kctl_odoo.commands.tenants import app as tenants_app
from kctl_odoo.commands.testing import app as testing_app
from kctl_odoo.commands.traceback_cmd import app as traceback_app
from kctl_odoo.commands.translations_cmd import app as translations_app
from kctl_odoo.commands.troubleshoot import app as troubleshoot_app
from kctl_odoo.commands.users import app as users_app
from kctl_odoo.commands.views import app as views_app
from kctl_odoo.commands.website_cmd import app as website_app
from kctl_odoo.commands.workers import app as workers_app
from kctl_odoo.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-odoo {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-odoo",
    help="Kodemeio Odoo CLI - manage your Odoo 18 ERP instances.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit table headers (for scripting)")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Odoo URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Database override")] = None,
    username: Annotated[str | None, typer.Option("--username", "-u", help="Username override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Odoo CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or output_format == "json",
        quiet=quiet,
        format=output_format,
        no_header=no_header,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
        database_override=database,
        username_override=username,
    )


# ---------------------------------------------------------------------------
# Register command groups with rich_help_panel for organized --help output
# ---------------------------------------------------------------------------

# --- Admin & Config ---
_P_ADMIN = "Admin & Config"
app.add_typer(config_app, name="config", rich_help_panel=_P_ADMIN)
app.add_typer(users_app, name="users", rich_help_panel=_P_ADMIN)
app.add_typer(companies_app, name="companies", rich_help_panel=_P_ADMIN)
app.add_typer(partners_app, name="partners", rich_help_panel=_P_ADMIN)
app.add_typer(security_app, name="security", rich_help_panel=_P_ADMIN)
app.add_typer(sessions_app, name="sessions", rich_help_panel=_P_ADMIN)
app.add_typer(databases_app, name="databases", rich_help_panel=_P_ADMIN)

# --- Business Operations ---
_P_BIZ = "Business Operations"
app.add_typer(sales_app, name="sales", rich_help_panel=_P_BIZ)
app.add_typer(purchasing_app, name="purchasing", rich_help_panel=_P_BIZ)
app.add_typer(inventory_app, name="inventory", rich_help_panel=_P_BIZ)
app.add_typer(accounting_app, name="accounting", rich_help_panel=_P_BIZ)
app.add_typer(hr_app, name="hr", rich_help_panel=_P_BIZ)
app.add_typer(onboarding_app, name="onboarding", rich_help_panel=_P_BIZ)
app.add_typer(mrp_app, name="mrp", rich_help_panel=_P_BIZ)
app.add_typer(pos_app, name="pos", rich_help_panel=_P_BIZ)
app.add_typer(project_app, name="project", rich_help_panel=_P_BIZ)
app.add_typer(dashboard_app, name="dashboard", rich_help_panel=_P_BIZ)
app.add_typer(products_app, name="products", rich_help_panel=_P_BIZ)
app.add_typer(crm_app, name="crm", rich_help_panel=_P_BIZ)
app.add_typer(delivery_app, name="delivery", rich_help_panel=_P_BIZ)

# --- Finance ---
_P_FIN = "Finance"
app.add_typer(tax_app, name="tax", rich_help_panel=_P_FIN)
app.add_typer(budget_app, name="budget", rich_help_panel=_P_FIN)
app.add_typer(dunning_app, name="dunning", rich_help_panel=_P_FIN)
app.add_typer(statements_app, name="statements", rich_help_panel=_P_FIN)
app.add_typer(assets_app, name="assets", rich_help_panel=_P_FIN)
app.add_typer(bank_app, name="bank", rich_help_panel=_P_FIN)
app.add_typer(payment_gateways_app, name="payment-gateways", rich_help_panel=_P_FIN)
app.add_typer(currency_app, name="currency", rich_help_panel=_P_FIN)

# --- Domain Management ---
_P_DOMAIN = "Domain Management"
app.add_typer(website_app, name="website", rich_help_panel=_P_DOMAIN)
app.add_typer(fleet_app, name="fleet", rich_help_panel=_P_DOMAIN)
app.add_typer(helpdesk_app, name="helpdesk", rich_help_panel=_P_DOMAIN)
app.add_typer(events_app, name="events", rich_help_panel=_P_DOMAIN)
app.add_typer(approvals_app, name="approvals", rich_help_panel=_P_DOMAIN)
app.add_typer(forms_app, name="forms", rich_help_panel=_P_DOMAIN)
app.add_typer(compliance_app, name="compliance", rich_help_panel=_P_DOMAIN)
app.add_typer(quality_app, name="quality", rich_help_panel=_P_DOMAIN)
app.add_typer(support_app, name="support", rich_help_panel=_P_DOMAIN)

# --- Reports & Analytics ---
_P_REPORT = "Reports & Analytics"
app.add_typer(report_app, name="report", rich_help_panel=_P_REPORT)
# Mount the report.template management sub-group under `report template ...`
report_app.add_typer(report_template_app, name="template")
report_app.add_typer(report_type_app, name="type")
report_app.add_typer(report_format_app, name="format")
report_app.add_typer(report_subkpi_app, name="subkpi")
report_app.add_typer(report_custom_query_app, name="custom-query")
report_app.add_typer(report_drill_route_app, name="drill-route")
report_app.add_typer(report_schedule_app, name="schedule")
app.add_typer(report_formats_app, name="report-formats", rich_help_panel=_P_REPORT)
app.add_typer(kpi_app, name="kpi", rich_help_panel=_P_REPORT)
app.add_typer(mis_reports_app, name="mis-reports", rich_help_panel=_P_REPORT)
app.add_typer(data_quality_app, name="data-quality", rich_help_panel=_P_REPORT)
app.add_typer(sql_export_app, name="sql-export", rich_help_panel=_P_REPORT)

# --- Infrastructure ---
_P_INFRA = "Infrastructure"
app.add_typer(troubleshoot_app, name="doctor", rich_help_panel=_P_INFRA)
app.add_typer(monitor_app, name="monitor", rich_help_panel=_P_INFRA)
app.add_typer(auto_maintain_app, name="auto-maintain", rich_help_panel=_P_INFRA)
app.add_typer(backup_app, name="backup", rich_help_panel=_P_INFRA)
app.add_typer(deploy_app, name="deploy", rich_help_panel=_P_INFRA)
app.add_typer(workers_app, name="workers", rich_help_panel=_P_INFRA)
app.add_typer(mail_app, name="mail", rich_help_panel=_P_INFRA)
app.add_typer(cron_app, name="cron", rich_help_panel=_P_INFRA)
app.add_typer(jobs_app, name="jobs", rich_help_panel=_P_INFRA)
app.add_typer(storage_app, name="storage", rich_help_panel=_P_INFRA)
app.add_typer(performance_app, name="performance", rich_help_panel=_P_INFRA)
app.add_typer(logs_app, name="logs", rich_help_panel=_P_INFRA)
app.add_typer(integration_app, name="integration", rich_help_panel=_P_INFRA)
app.add_typer(accurate_app, name="accurate", rich_help_panel=_P_INFRA)
app.add_typer(maintenance_app, name="maintenance", rich_help_panel=_P_INFRA)
app.add_typer(audit_app, name="audit", rich_help_panel=_P_INFRA)

# --- Development ---
_P_DEV = "Development"
app.add_typer(dev_app, name="dev", rich_help_panel=_P_DEV)
app.add_typer(lint_app, name="lint", rich_help_panel=_P_DEV)
app.add_typer(testing_app, name="test", rich_help_panel=_P_DEV)
app.add_typer(generate_app, name="scaffold", rich_help_panel=_P_DEV)
app.add_typer(manifest_app, name="manifest", rich_help_panel=_P_DEV)
app.add_typer(views_app, name="views", rich_help_panel=_P_DEV)
app.add_typer(orm_app, name="orm", rich_help_panel=_P_DEV)
app.add_typer(record_rules_app, name="record-rules", rich_help_panel=_P_DEV)
app.add_typer(traceback_app, name="traceback", rich_help_panel=_P_DEV)
app.add_typer(translations_app, name="translations", rich_help_panel=_P_DEV)
app.add_typer(fastapi_app, name="fastapi", rich_help_panel=_P_DEV)
app.add_typer(dev_mode_app, name="dev-mode", rich_help_panel=_P_DEV)
app.add_typer(e2e_app, name="e2e", rich_help_panel=_P_DEV)

# --- Instance Management ---
_P_INSTANCE = "Instance Management"
app.add_typer(local_app, name="local", rich_help_panel=_P_INSTANCE)
app.add_typer(modules_app, name="modules", rich_help_panel=_P_INSTANCE)
app.add_typer(bundles_app, name="bundles", rich_help_panel=_P_INSTANCE)
app.add_typer(roles_app, name="roles", rich_help_panel=_P_INSTANCE)
app.add_typer(addons_app, name="addons", rich_help_panel=_P_INSTANCE)
app.add_typer(tenants_app, name="tenants", rich_help_panel=_P_INSTANCE)
app.add_typer(setup_app, name="setup", rich_help_panel=_P_INSTANCE)
app.add_typer(pipeline_app, name="pipeline", rich_help_panel=_P_INSTANCE)
app.add_typer(diff_app, name="diff", rich_help_panel=_P_INSTANCE)
app.add_typer(config_server_app, name="server", rich_help_panel=_P_INSTANCE)
app.add_typer(configure_app, name="master-data", rich_help_panel=_P_INSTANCE)
app.add_typer(pricelist_app, name="pricelist", rich_help_panel=_P_BIZ)
app.add_typer(automation_app, name="automation", rich_help_panel=_P_INSTANCE)
app.add_typer(sequences_app, name="sequences", rich_help_panel=_P_INSTANCE)
app.add_typer(periods_app, name="periods", rich_help_panel=_P_INSTANCE)
app.add_typer(cleanup_app, name="clean", rich_help_panel=_P_INSTANCE)
app.add_typer(migrate_app, name="migrate", rich_help_panel=_P_INSTANCE)
app.add_typer(staging_app, name="staging", rich_help_panel=_P_INSTANCE)

# --- Tools ---
_P_TOOLS = "Tools"
app.add_typer(shell_app, name="shell", rich_help_panel=_P_TOOLS)
app.add_typer(repl_app, name="repl", rich_help_panel=_P_TOOLS)
app.add_typer(export_app, name="export", rich_help_panel=_P_TOOLS)
app.add_typer(import_app, name="import", rich_help_panel=_P_TOOLS)
app.add_typer(history_app, name="history", rich_help_panel=_P_TOOLS)
app.add_typer(self_test_app, name="self-test", rich_help_panel=_P_TOOLS)
app.add_typer(skill_app, name="skill", rich_help_panel=_P_TOOLS)

# ---------------------------------------------------------------------------
# Short aliases for common workflows (hidden from --help)
# ---------------------------------------------------------------------------
from kctl_odoo.commands.aliases import register_aliases  # noqa: E402

register_aliases(app)

# ---------------------------------------------------------------------------
# Load plugins via entry points
# ---------------------------------------------------------------------------
from kctl_odoo.core.plugins import discover_and_load_plugins  # noqa: E402

discover_and_load_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-odoo."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-odoo", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-odoo")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command()
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-odoo", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-odoo", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
