"""`stare index ...` commands (mounted by the CLI team via ``app.add_typer(index_app(), name="index")``)."""

from __future__ import annotations

import typer


def index_app() -> typer.Typer:
    app = typer.Typer(help="Build and query the hybrid retrieval index.", no_args_is_help=True)

    @app.command()
    def build() -> None:
        """Fit the embedder, embed every chunk and build the BM25 index."""
        from stare.config import get_settings
        from stare.db.session import init_db, session_scope
        from stare.retrieval.hybrid import HybridRetriever, IndexNotBuiltError

        settings = get_settings()
        init_db()
        try:
            with session_scope() as s:
                stats = HybridRetriever.build_index(s, settings)
        except IndexNotBuiltError as e:
            typer.secho(str(e), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from e
        typer.echo(f"Indexed {stats['chunks']} chunks ({stats['terms']} terms, dim {stats['dim']}) -> {settings.index_dir}")

    @app.command()
    def search(query: str, k: int = typer.Option(10, "--k", "-k", help="Number of chunks")) -> None:
        """Run a hybrid search and print the results."""
        from stare.db.session import get_sessionmaker
        from stare.retrieval.hybrid import HybridRetriever, IndexNotBuiltError, IndexStaleError

        retriever = HybridRetriever(get_sessionmaker())
        try:
            chunks = retriever.search(query, k=k)
        except (IndexNotBuiltError, IndexStaleError) as e:
            typer.secho(str(e), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from e
        auth = {a.opinion_id or -(a.section_id or 0): a for a in retriever.authorities_from_chunks(chunks, k)}
        for i, c in enumerate(chunks, 1):
            a = auth.get(c.opinion_id or -(c.section_id or 0))
            label = f"{a.citation} {a.case_name}".strip() if a else f"chunk {c.chunk_id}"
            typer.echo(
                f"{i:>2}. [{c.kind}] {label}  (bm25={c.bm25_rank} dense={c.dense_rank} rerank={c.rerank_score})\n"
                f"    {c.text[:160].replace(chr(10), ' ')}"
            )

    return app
