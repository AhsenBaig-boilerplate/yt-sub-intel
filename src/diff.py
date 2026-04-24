"""
Change detection between two enriched DataFrames.
Compares by channel_id and reports new, removed, and modified channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import polars as pl

CLASSIFICATION_COLS = [
    "primary_category",
    "secondary_category",
    "political_lean",
    "tone_style",
    "risk_score",
    "enrichment_source",
]


@dataclass
class DiffReport:
    new_channels: List[str] = field(default_factory=list)
    removed_channels: List[str] = field(default_factory=list)
    modified_channels: List[Dict] = field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.new_channels or self.removed_channels or self.modified_channels)

    def summary(self) -> str:
        lines = [
            f"  New channels:      {len(self.new_channels)}",
            f"  Removed channels:  {len(self.removed_channels)}",
            f"  Modified channels: {len(self.modified_channels)}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "new_channels": self.new_channels,
            "removed_channels": self.removed_channels,
            "modified_channels": self.modified_channels,
        }


def compute_diff(existing: pl.DataFrame, incoming: pl.DataFrame) -> DiffReport:
    """Compare existing (previous run) vs incoming (current run) DataFrames."""
    report = DiffReport()

    existing_ids = set(existing["channel_id"].to_list())
    incoming_ids = set(incoming["channel_id"].to_list())

    report.new_channels = sorted(incoming_ids - existing_ids)
    report.removed_channels = sorted(existing_ids - incoming_ids)

    shared_ids = existing_ids & incoming_ids
    if not shared_ids:
        return report

    ex_shared = existing.filter(pl.col("channel_id").is_in(shared_ids)).sort("channel_id")
    in_shared = incoming.filter(pl.col("channel_id").is_in(shared_ids)).sort("channel_id")

    for col in CLASSIFICATION_COLS:
        if col not in ex_shared.columns or col not in in_shared.columns:
            continue

        changed = (
            ex_shared.select(["channel_id", "channel_title", col])
            .rename({col: f"old_{col}"})
            .join(
                in_shared.select(["channel_id", col]).rename({col: f"new_{col}"}),
                on="channel_id",
                how="inner",
            )
            .filter(pl.col(f"old_{col}") != pl.col(f"new_{col}"))
        )

        for row in changed.to_dicts():
            report.modified_channels.append({
                "channel_id": row["channel_id"],
                "channel_title": row["channel_title"],
                "field": col,
                "old_value": str(row[f"old_{col}"]),
                "new_value": str(row[f"new_{col}"]),
            })

    return report
