"""
Classification engine for YouTube channels.

Resolution order:
  1. Exact match by channel_id in channel_classifications.json
  2. Exact match by channel_title (case-insensitive) in channel_classifications.json
  3. First matching regex rule in keyword_rules.json
  4. Default "Unknown" classification
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.schema import ENRICHMENT_VERSION, RISK_FLAG_COLUMNS

_DEFAULT_CLASSIFICATION: Dict[str, Any] = {
    "primary_category": "Unknown",
    "secondary_category": "",
    "political_lean": "unknown",
    "content_domains": [],
    "tone_style": "unknown",
    "risk_flags": {},
    "notes": "",
    "tone_shift": None,
    "enrichment_source": "default",
}


class Classifier:
    def __init__(self, classifications_path: Path, rules_path: Path) -> None:
        self._by_id: Dict[str, Dict] = {}
        self._by_title: Dict[str, Dict] = {}
        self._rules: List[Dict] = []
        self._load(classifications_path, rules_path)

    def _load(self, classifications_path: Path, rules_path: Path) -> None:
        with open(classifications_path) as f:
            data = json.load(f)
        for channel in data.get("channels", []):
            cid = channel.get("channel_id", "").strip()
            ctitle = channel.get("channel_title", "").strip().lower()
            if cid:
                self._by_id[cid] = channel
            if ctitle:
                self._by_title[ctitle] = channel

        with open(rules_path) as f:
            rdata = json.load(f)
        for rule in rdata.get("rules", []):
            self._rules.append({
                **rule,
                "_compiled": re.compile(rule["pattern"]),
            })

    def classify(self, channel_id: str, channel_title: str) -> dict[str, Any]:
        record = (
            self._by_id.get(channel_id.strip())
            or self._by_title.get(channel_title.strip().lower())
        )
        source = "manual"

        if record is None:
            for rule in self._rules:
                if rule["_compiled"].search(channel_title):
                    record = rule
                    source = "keyword_rule"
                    break

        if record is None:
            record = _DEFAULT_CLASSIFICATION
            source = "default"

        return self._build_row(record, source)

    def _build_row(self, record: Dict, source: str) -> Dict[str, Any]:
        raw_flags: dict = record.get("risk_flags", {})

        risk_cols: Dict[str, bool] = {}
        for col in RISK_FLAG_COLUMNS:
            flag_key = col[len("risk_"):]
            risk_cols[col] = bool(raw_flags.get(flag_key, False))

        risk_score = sum(risk_cols.values())

        domains = record.get("content_domains", [])
        content_domains_str = json.dumps(domains) if domains else "[]"

        tone_shift: Optional[Dict] = record.get("tone_shift")

        row: dict[str, Any] = {
            "primary_category": record.get("primary_category", "Unknown"),
            "secondary_category": record.get("secondary_category", ""),
            "political_lean": record.get("political_lean", "unknown"),
            "content_domains": content_domains_str,
            "tone_style": record.get("tone_style", "unknown"),
            **risk_cols,
            "risk_score": risk_score,
            "notes": record.get("notes", ""),
            "tone_shift_detected": bool(tone_shift),
            "tone_shift_date": (tone_shift or {}).get("shift_date", ""),
            "tone_shift_from": (tone_shift or {}).get("from_tone", ""),
            "tone_shift_to": (tone_shift or {}).get("to_tone", ""),
            "tone_shift_notes": (tone_shift or {}).get("notes", ""),
            "enrichment_version": ENRICHMENT_VERSION,
            "enrichment_source": source,
        }
        return row
