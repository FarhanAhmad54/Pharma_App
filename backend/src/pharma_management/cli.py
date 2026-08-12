import typer

from pharma_management.config import get_settings

app = typer.Typer(help="Pharmaceutical Management System")


@app.command()
def health() -> None:
    """Print configured backend environment."""
    settings = get_settings()
    typer.echo(f"{settings.app_name} [{settings.environment}]")
    typer.echo("Use the FastAPI service for database-backed operations: uvicorn pharma_management.api:app")


if __name__ == "__main__":
    app()
