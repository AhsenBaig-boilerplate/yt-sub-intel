from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Set

import polars as pl

from yt_sub_intel.classifier import Classifier
from yt_sub_intel.diff import compute_diff
from yt_sub_intel.schema import POLARS_SCHEMA

TAKEOUT_COL_MAP = {
    "Channel Id": "channel_id",
    "Channel Url": "channel_url",
    "Channel Title": "channel_title",
}
RAW_REQUIRED_COLS = {"Channel Id", "Channel Url", "Channel Title"}


def _read_raw_csv(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=0)
    missing = RAW_REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Raw CSV missing columns: {missing}\n"
            f"Found: {df.columns}\n"
            "Expected Google Takeout format: 'Channel Id', 'Channel Url', 'Channel Title'"
        )
    return df.rename({k: v for k, v in TAKEOUT_COL_MAP.items() if k in df.columns})


def _cast_schema(df: pl.DataFrame) -> pl.DataFrame:
    casts = []
    for col, dtype in POLARS_SCHEMA.items():
        if col in df.columns:
            casts.append(pl.col(col).cast(dtype))
        else:
            if dtype == pl.Boolean:
                casts.append(pl.lit(False).alias(col).cast(dtype))
            elif dtype == pl.Int32:
                casts.append(pl.lit(0).alias(col).cast(dtype))
            else:
                casts.append(pl.lit("").alias(col).cast(dtype))
    return df.with_columns(casts).select(list(POLARS_SCHEMA.keys()))


def _enrich_dataframe(
    raw: pl.DataFrame,
    classifier: Classifier,
    today: str,
    existing: Optional[pl.DataFrame],
) -> pl.DataFrame:
    rows = []
    existing_by_id: Dict[str, Dict] = {}
    if existing is not None:
        existing_by_id = {r["channel_id"]: r for r in existing.to_dicts()}

    for row in raw.to_dicts():
        cid = (row.get("channel_id") or "").strip()
        curl = (row.get("channel_url") or "").strip()
        ctitle = (row.get("channel_title") or "").strip()

        cls = classifier.classify(cid, ctitle)
        prev = existing_by_id.get(cid)
        first_seen = prev["first_seen_date"] if prev else today

        # Preserve manually edited tone_shift history
        if prev and prev.get("tone_shift_detected") and not cls["tone_shift_detected"]:
            for f in ("tone_shift_detected", "tone_shift_date", "tone_shift_from",
                      "tone_shift_to", "tone_shift_notes"):
                cls[f] = prev[f]

        # Preserve manual notes when new classification has none
        if prev and prev.get("notes") and not cls["notes"]:
            cls["notes"] = prev["notes"]

        record: Dict[str, Any] = {
            "channel_id": cid,
            "channel_url": curl,
            "channel_title": ctitle,
            **cls,
            "first_seen_date": first_seen,
            "last_seen_date": today,
            "status": "active",
        }
        rows.append(record)

    return _cast_schema(pl.DataFrame(rows))


def _mark_removed(existing: pl.DataFrame, incoming_ids: Set[str], today: str) -> pl.DataFrame:
    return existing.filter(
        ~pl.col("channel_id").is_in(incoming_ids) & (pl.col("status") == "active")
    ).with_columns(pl.lit("removed").alias("status"))


def run(
    raw_csv: Path,
    output_dir: Path,
    classifications_path: Path,
    rules_path: Path,
) -> None:
    today = str(date.today())
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir / "subscriptions_enriched.parquet"
    csv_path = output_dir / "subscriptions_enriched.csv"
    diff_path = output_dir / "diff_report.json"

    print(f"[yt-sub-intel] Reading raw CSV: {raw_csv}")
    raw = _read_raw_csv(raw_csv)
    print(f"[yt-sub-intel] Found {len(raw)} channels in raw CSV")

    classifier = Classifier(classifications_path, rules_path)

    existing: Optional[pl.DataFrame] = None
    if parquet_path.exists():
        existing = pl.read_parquet(parquet_path)
        print(f"[yt-sub-intel] Loaded existing Parquet with {len(existing)} records")

    enriched = _enrich_dataframe(raw, classifier, today, existing)

    diff_report = None
    if existing is not None:
        diff_report = compute_diff(existing.filter(pl.col("status") == "active"), enriched)

        removed = _mark_removed(existing, set(enriched["channel_id"].to_list()), today)
        prev_removed = existing.filter(pl.col("status") == "removed").filter(
            ~pl.col("channel_id").is_in(enriched["channel_id"].to_list())
        )
        if not removed.is_empty():
            prev_removed = (
                pl.concat([prev_removed, removed]) if not prev_removed.is_empty() else removed
            )
        if not prev_removed.is_empty():
            enriched = pl.concat([enriched, _cast_schema(prev_removed)])

    print(f"[yt-sub-intel] Writing enriched CSV:     {csv_path}")
    enriched.write_csv(csv_path)
    print(f"[yt-sub-intel] Writing enriched Parquet: {parquet_path}")
    enriched.write_parquet(parquet_path, compression="snappy")

    if diff_report is not None:
        diff_path.write_text(json.dumps(diff_report.to_dict(), indent=2))
        print(f"[yt-sub-intel] Writing diff report:      {diff_path}")
        print("\n[yt-sub-intel] Change summary:")
        print(diff_report.summary())
    else:
        print("[yt-sub-intel] First import — no diff computed")

    active_count = len(enriched.filter(pl.col("status") == "active"))
    flagged_count = len(enriched.filter(pl.col("risk_score") > 0))
    print(f"\n[yt-sub-intel] Done.")
    print(f"  Active channels:   {active_count}")
    print(f"  Flagged channels:  {flagged_count}")
    print(f"  Output:            {output_dir.resolve()}")
