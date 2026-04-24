"""
Canonical field schema for the enriched YouTube subscription dataset.
"""

from __future__ import annotations

from typing import Dict

import polars as pl

ENRICHMENT_VERSION = "1.0.0"

RISK_FLAG_COLUMNS = [
    "risk_white_supremacy",
    "risk_ethnonationalism",
    "risk_anti_immigrant_extremism",
    "risk_antisemitism",
    "risk_anti_black_rhetoric",
    "risk_anti_lgbtq_extremism",
    "risk_religious_extremism",
    "risk_conspiracy_driven",
    "risk_harassment_mobs",
    "risk_misinformation_pattern",
]

POLARS_SCHEMA: Dict[str, pl.DataType] = {
    "channel_id":                    pl.Utf8,
    "channel_url":                   pl.Utf8,
    "channel_title":                 pl.Utf8,
    "primary_category":              pl.Utf8,
    "secondary_category":            pl.Utf8,
    "political_lean":                pl.Utf8,
    "content_domains":               pl.Utf8,
    "tone_style":                    pl.Utf8,
    "risk_white_supremacy":          pl.Boolean,
    "risk_ethnonationalism":         pl.Boolean,
    "risk_anti_immigrant_extremism": pl.Boolean,
    "risk_antisemitism":             pl.Boolean,
    "risk_anti_black_rhetoric":      pl.Boolean,
    "risk_anti_lgbtq_extremism":     pl.Boolean,
    "risk_religious_extremism":      pl.Boolean,
    "risk_conspiracy_driven":        pl.Boolean,
    "risk_harassment_mobs":          pl.Boolean,
    "risk_misinformation_pattern":   pl.Boolean,
    "risk_score":                    pl.Int32,
    "notes":                         pl.Utf8,
    "tone_shift_detected":           pl.Boolean,
    "tone_shift_date":               pl.Utf8,
    "tone_shift_from":               pl.Utf8,
    "tone_shift_to":                 pl.Utf8,
    "tone_shift_notes":              pl.Utf8,
    "first_seen_date":               pl.Utf8,
    "last_seen_date":                pl.Utf8,
    "status":                        pl.Utf8,
    "enrichment_version":            pl.Utf8,
    "enrichment_source":             pl.Utf8,
}
