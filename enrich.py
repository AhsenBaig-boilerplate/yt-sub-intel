#!/usr/bin/env python3
"""
CLI entrypoint: yt-sub-intel enrichment pipeline.

Usage:
    python enrich.py
    python enrich.py --raw data/subscriptions_raw.csv --output output/
    python enrich.py --raw path/to/subscriptions.csv --output path/to/out/
"""

import sys
from pathlib import Path

import click

HERE = Path(__file__).parent
DEFAULT_RAW = HERE / "data" / "subscriptions_raw.csv"
DEFAULT_OUTPUT = HERE / "output"
DEFAULT_CLASSIFICATIONS = HERE / "mappings" / "channel_classifications.json"
DEFAULT_RULES = HERE / "mappings" / "keyword_rules.json"


@click.command()
@click.option(
    "--raw", "-r",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_RAW,
    show_default=True,
    help="Path to raw Google Takeout subscriptions CSV",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    show_default=True,
    help="Directory for enriched outputs (CSV, Parquet, diff report)",
)
@click.option(
    "--classifications", "-c",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CLASSIFICATIONS,
    show_default=True,
    help="Path to channel_classifications.json",
)
@click.option(
    "--rules",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_RULES,
    show_default=True,
    help="Path to keyword_rules.json",
)
def main(
    raw: Path,
    output: Path,
    classifications: Path,
    rules: Path,
) -> None:
    """Enrich a YouTube Takeout subscriptions CSV with categories, political lean, and risk flags."""
    try:
        from src.enricher import run
        run(
            raw_csv=raw,
            output_dir=output,
            classifications_path=classifications,
            rules_path=rules,
        )
    except ImportError as e:
        click.echo(f"[error] Missing dependency: {e}", err=True)
        click.echo("Run: pip install -r requirements.txt", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"[error] {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
