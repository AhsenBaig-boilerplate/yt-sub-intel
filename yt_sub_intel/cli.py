import sys
from pathlib import Path

import click

HERE = Path(__file__).parent.parent
DEFAULT_RAW = HERE / "data" / "subscriptions_raw.csv"
DEFAULT_OUTPUT = HERE / "output"
DEFAULT_CLASSIFICATIONS = HERE / "mappings" / "channel_classifications.json"
DEFAULT_RULES = HERE / "mappings" / "keyword_rules.json"


@click.command()
@click.option("--raw", "-r", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_RAW, show_default=True,
              help="Path to raw Google Takeout subscriptions CSV")
@click.option("--output", "-o", type=click.Path(path_type=Path),
              default=DEFAULT_OUTPUT, show_default=True,
              help="Output directory for enriched CSV, Parquet, and diff report")
@click.option("--classifications", "-c", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CLASSIFICATIONS, show_default=True,
              help="Path to channel_classifications.json")
@click.option("--rules", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_RULES, show_default=True,
              help="Path to keyword_rules.json")
@click.option("--llm-classify", is_flag=True, default=False,
              help=(
                  "Use the Claude API to classify channels that match no manual entry or "
                  "keyword rule. Requires ANTHROPIC_API_KEY in the environment."
              ))
@click.option("--model", default="claude-haiku-4-5", show_default=True,
              help="Claude model for LLM classification (e.g. claude-haiku-4-5, claude-sonnet-4-6)")
@click.option("--llm-cache", type=click.Path(path_type=Path), default=None,
              help="Path to LLM classification cache JSON (default: mappings/llm_cache.json)")
def main(
    raw: Path,
    output: Path,
    classifications: Path,
    rules: Path,
    llm_classify: bool,
    model: str,
    llm_cache: Path,
) -> None:
    """Enrich a YouTube Takeout subscriptions CSV with categories, political lean, and risk flags."""
    try:
        from yt_sub_intel.enricher import run
        run(
            raw_csv=raw,
            output_dir=output,
            classifications_path=classifications,
            rules_path=rules,
            llm_classify=llm_classify,
            llm_model=model,
            llm_cache_path=llm_cache,
        )
    except Exception as e:
        click.echo(f"[error] {e}", err=True)
        sys.exit(1)
