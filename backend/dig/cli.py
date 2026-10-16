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
    repo: str | None = typer.Option(None, "--repo", help="Target repository (OWNER/REPO)"),
    threshold: int = typer.Option(2, "--threshold", help="Signal threshold filter"),
) -> None:
    """Extract decisions from ingested threads using LLM and verify quotes."""
    from dig.extract.extractor import DecisionExtractor
    from dig.extract.signals import filter_threads
    from dig.graph.loader import load_decisions
    from dig.ingest.cache import load_normalized_threads

    target = repo or settings.target_repo
    threads = load_normalized_threads(target)
    if not threads:
        typer.echo(f"No threads found for {target}. Run dig ingest first.")
        return

    qualifying = filter_threads(threads, threshold=threshold)
    typer.echo(
        f"Total threads: {len(threads)}, Qualifying (threshold >= {threshold}): {len(qualifying)}"
    )

    extractor = DecisionExtractor()
    candidate_threads = [t for t, _ in qualifying]

    async def _run() -> None:
        decisions, stats = await extractor.extract_and_verify_all(candidate_threads)
        typer.echo(f"Threads sent: {stats['threads_sent']}")
        typer.echo(f"Decisions extracted: {stats['decisions_extracted']}")
        typer.echo(f"Decisions verified: {stats['decisions_verified']}")
        typer.echo(f"Evidence kept: {stats['evidence_kept']}, dropped: {stats['evidence_dropped']}")

        # Show sample verified decisions with quotes
        if decisions:
            typer.echo("\n--- Sample Verified Decisions ---")
            for d in decisions[:5]:
                quotes = [ev.get("quote") for ev in d.get("evidence", [])]
                typer.echo(f"* [{d.get('type')}] {d.get('title')}")
                for q in quotes:
                    typer.echo(f'    Evidence quote: "{q}"')

        # Load into FalkorDB
        load_res = load_decisions(decisions=decisions)
        typer.echo(
            f"FalkorDB Decision count: {load_res['decisions']}, Evidence count: {load_res['evidence']}"
        )

    asyncio.run(_run())


@app.command()
def link(
    max_pairs: int = typer.Option(600, "--max-pairs", help="Maximum candidate pairs to evaluate"),
    min_confidence: float = typer.Option(
        0.6, "--min-confidence", help="Minimum confidence threshold"
    ),
) -> None:
    """Link extracted decisions (supersedes, reverses, depends_on, conflicts_with)."""
    from dig.extract.linker import DecisionLinker

    typer.echo(
        f"Linking decisions (max {max_pairs} candidate pairs, min confidence {min_confidence})..."
    )
    linker = DecisionLinker()

    async def _run() -> None:
        res = await linker.link_decisions(max_pairs=max_pairs, min_confidence=min_confidence)
        typer.echo(f"Linking complete! Counts by relation type: {res['counts']}")
        if res.get("chains"):
            typer.echo("\n--- Sample Decision Chains ---")
            for c in res["chains"][:5]:
                typer.echo(
                    f'* [{c["relation"].upper()}] "{c["newer"]}" ({c.get("newer_date")}) -> "{c["older"]}" ({c.get("older_date")}) [conf={c["confidence"]}]'
                )

    asyncio.run(_run())


@app.command()
def score() -> None:
    """Compute and write KNOWS expertise scores for (Person, Module)."""
    from dig.extract.expertise import compute_and_write_expertise

    typer.echo("Computing and scoring module expertise with recency decay...")
    res = compute_and_write_expertise()
    typer.echo(f"Successfully wrote {res['knows_edges']} KNOWS edges.")

    top_people = res.get("top_per_module", {})
    if top_people:
        typer.echo("\n--- Top Experts by Module ---")
        for mod, people in top_people.items():
            if people:
                typer.echo(f"Module: {mod}")
                for p in people:
                    typer.echo(
                        f"  * {p['login']:<15} score={p['score']:<5} (authored={p['authored']}, reviewed={p['reviewed']}, commented={p['commented']})"
                    )


@app.command()
def sync(
    repo: str | None = typer.Option(None, "--repo", help="Target repository"),
) -> None:
    """Run incremental sync for newly updated threads and decisions."""
    from dig.sync import run_incremental_sync

    typer.echo("Running incremental sync with GitHub...")

    async def _run():
        res = await run_incremental_sync(repo=repo)
        typer.echo(
            f"Sync complete! Threads updated: {res['threads_updated']}, Decisions added: {res['decisions_added']}"
        )
        typer.echo(f"Last synced timestamp: {res['last_synced']}")

    asyncio.run(_run())


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask Decision Archaeologist"),
    repo: str | None = typer.Option(None, "--repo", help="Target repository"),
) -> None:
    """Ask Decision Archaeologist a question about repository choices and ownership."""
    from dig.agent.agent import DecisionAgent

    target_repo = repo or settings.target_repo
    agent = DecisionAgent(repo=target_repo)

    async def _run() -> None:
        typer.echo(f"\nQuestion: {question}")
        typer.echo("Thinking and querying repository decision graph...\n")

        async for ev in agent.ask_stream(question):
            if ev.event == "tool_call":
                name = ev.data.get("name")
                inp = ev.data.get("input")
                typer.echo(f"  [Tool Call]   {name}({inp})")
            elif ev.event == "tool_result":
                name = ev.data.get("name")
                summary = ev.data.get("summary")
                typer.echo(f"  [Tool Result] {name} -> {summary}")
            elif ev.event == "answer":
                typer.echo("\n" + "=" * 50)
                typer.echo("ANSWER:\n")
                typer.echo(ev.data.get("markdown", ""))
                typer.echo("\n" + "-" * 50)
                typer.echo("CITATIONS:")
                citations = ev.data.get("citations", [])
                if citations:
                    for c in citations:
                        typer.echo(
                            f"  [{c['n']}] \"{c['quote']}\"\n      Author: {c['author']} | URL: {c['url']}"
                        )
                else:
                    typer.echo("  (No direct citations)")

                typer.echo("\nVERIFICATION TRUST BADGE:")
                v = ev.data.get("verification", {})
                badge = (
                    "Verified against graph"
                    if v.get("invalid", 0) == 0
                    else "Unverified claims detected"
                )
                typer.echo(
                    f"  Status: {badge} (valid: {v.get('valid')}, invalid: {v.get('invalid')}, repaired: {v.get('repaired')})"
                )
                typer.echo("=" * 50 + "\n")
            elif ev.event == "error":
                typer.secho(f"Error: {ev.data.get('message')}", fg=typer.colors.RED)

    asyncio.run(_run())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", help="Server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable hot reload"),
) -> None:
    """Start the FastAPI backend server."""
    import uvicorn

    typer.echo(f"Starting Decision Archaeologist API server on {host}:{port}...")
    uvicorn.run("dig.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
