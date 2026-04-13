import typer

app = typer.Typer(help="TODO: replace in later task", no_args_is_help=True)


@app.command("placeholder", hidden=True)
def _placeholder() -> None:
    raise typer.Exit()
