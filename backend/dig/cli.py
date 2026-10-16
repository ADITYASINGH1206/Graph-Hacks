"""CLI entrypoint for dig."""

import asyncio
import logging

import typer

from dig.config import settings

app = typer.Typer(help="Decision Archaeologist CLI: context layer for repository decision history.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@app.command()
def ingest(
    repo: str | None = typer.Option(None, "--repo", help="Target repository (OWNER/REPO)"),
    max_threads: int = typer.Option(1500, "--max-threads", help="Maximum threads to ingest"),
) -> None:
    """Ingest GitHub issues, PRs, comments, and releases."""
    from dig.ingest.github import GitHubClient

    target = repo or settings.target_repo
    typer.echo(f"Ingesting {target} (max {max_threads} threads)...")

    async def _run() -> None:
        client = GitHubClient(repo=target)
        try:
            threads = await client.ingest_repo(repo=target, max_threads=max_threads)
            typer.echo(
                f"Successfully ingested {len(threads)} threads. Total network calls: {client.network_calls_made}"
            )
        finally:
            await client.close()

    asyncio.run(_run())


@app.command("load-structure")
def load_structure_cmd(
    repo: str | None = typer.Option(None, "--repo", help="Target repository (OWNER/REPO)"),
    batch_size: int = typer.Option(500, "--batch-size", help="Batch size for UNWIND queries"),
) -> None:
    """Load structural nodes and edges into FalkorDB."""
    from dig.graph.loader import load_structure

    target = repo or settings.target_repo
    typer.echo(f"Loading structure into FalkorDB for {target}...")
    stats = load_structure(repo=target, batch_size=batch_size)
    typer.echo(f"Total Nodes: {stats.get('nodes', 0)}, Total Edges: {stats.get('edges', 0)}")
    typer.echo(f"Labels: {stats.get('labels')}")
    typer.echo(f"Edge Types: {stats.get('edge_types')}")


@app.command()
def extract(
    threshold: int | None = typer.Option(None, "--threshold", help="Signal threshold filter"),
) -> None:
    """Extract decisions from ingested threads using LLM and verify quotes."""
    typer.echo("Extracting decisions from threads...")


@app.command()
def link() -> None:
    """Link extracted decisions (supersedes, reverses, depends_on, conflicts_with)."""
    typer.echo("Linking decisions...")


@app.command()
def score() -> None:
    """Compute and write KNOWS expertise scores for (Person, Module)."""
    typer.echo("Scoring module expertise...")


@app.command()
def sync() -> None:
    """Run incremental sync for newly updated threads and decisions."""
    typer.echo("Running incremental sync...")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", help="Server port"),
) -> None:
    """Start the FastAPI backend server."""
    typer.echo(f"Starting API server on {host}:{port}...")


if __name__ == "__main__":
    app()
