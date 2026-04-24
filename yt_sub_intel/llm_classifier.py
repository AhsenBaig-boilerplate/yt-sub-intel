"""
LLM-assisted classification for channels that fall through keyword rules.

Uses the Anthropic API with:
- Tool use for reliable structured output
- Prompt caching on the system prompt (same for every channel)
- A local JSON cache so channels are never re-classified across runs
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

from yt_sub_intel.schema import ENRICHMENT_VERSION, RISK_FLAG_COLUMNS

# ── Enum values ───────────────────────────────────────────────────────────────

_PRIMARY_CATEGORIES = [
    "News & Politics", "Science & Education", "Technology", "Finance & Economics",
    "Gaming", "Entertainment", "Sports", "Health & Fitness", "Religion & Spirituality",
    "Arts & Culture", "Comedy & Satire", "Conspiracy & Fringe", "Activism & Advocacy",
    "Personal Finance", "History & Documentary", "Travel & Lifestyle", "Food & Cooking",
    "Music", "Other", "Unknown",
]

_POLITICAL_LEANS = [
    "far_left", "left", "center_left", "center", "center_right",
    "right", "far_right", "nonpartisan", "unknown",
]

_TONE_STYLES = [
    "analytical", "opinion", "broadcast", "documentary", "entertainment",
    "satire", "propaganda", "educational", "grassroots", "debate", "unknown",
]

# ── System prompt (cached across all channel calls) ───────────────────────────

_SYSTEM_PROMPT = """\
You are a YouTube channel content analyst with deep knowledge of online media, politics,
and extremism research. Given a channel title and URL, classify it using your training
knowledge of the channel where possible, or reasonable inference from its name otherwise.

PRIMARY CATEGORIES (choose one):
News & Politics, Science & Education, Technology, Finance & Economics, Gaming,
Entertainment, Sports, Health & Fitness, Religion & Spirituality, Arts & Culture,
Comedy & Satire, Conspiracy & Fringe, Activism & Advocacy, Personal Finance,
History & Documentary, Travel & Lifestyle, Food & Cooking, Music, Other, Unknown

POLITICAL LEAN (choose one):
- far_left: Revolutionary socialist, communist, anarchist, or anti-capitalist content
- left: Progressive, social-democratic, strongly liberal editorial direction
- center_left: Mainstream liberal, center-left perspective
- center: Genuinely balanced coverage of multiple perspectives
- center_right: Mainstream conservative, moderate right perspective
- right: Traditional conservative, clearly right-wing editorial direction
- far_right: Extreme right, nationalist, white identitarian, or authoritarian content
- nonpartisan: Explicitly non-political (science, gaming, cooking, sports entertainment)
- unknown: Cannot reasonably determine

TONE STYLE (choose one):
- analytical: Data-driven, research-based, measured and factual
- opinion: Editorial commentary, talking-head perspectives
- broadcast: Traditional news broadcast format
- documentary: Long-form investigative or narrative journalism
- entertainment: Primary purpose is entertainment and engagement
- satire: Comedy with political or social commentary
- propaganda: One-sided persuasion with distorted or misleading framing
- educational: Tutorials, explainers, how-to content
- grassroots: Independent or citizen journalism style
- debate: Structured adversarial discussion
- unknown: Cannot determine

RISK FLAGS — only set true with DOCUMENTED, SUBSTANTIATED evidence:
- white_supremacy: Explicit white supremacist ideology
- ethnonationalism: Ethnic/racial nationalist ideology (e.g. replacement theory)
- anti_immigrant_extremism: Extreme anti-immigration beyond normal policy debate
- antisemitism: Documented antisemitic content or Jewish conspiracy promotion
- anti_black_rhetoric: Anti-Black racism or documented racist framing
- anti_lgbtq_extremism: Extreme anti-LGBTQ+ content beyond traditional religious views
- religious_extremism: Religious extremism justifying violence or discrimination
- conspiracy_driven: Primary content is debunked conspiracies (QAnon, flat earth, etc.)
- harassment_mobs: Documented history directing followers to harass individuals
- misinformation_pattern: Documented pattern of publishing factually false content

CRITICAL: Conservative/right-wing lean alone does NOT warrant risk flags.
Unknown channels default all risk flags to false unless the name/URL is a clear indicator.\
"""

# ── Tool definition ───────────────────────────────────────────────────────────

_CLASSIFY_TOOL: Dict[str, Any] = {
    "name": "classify_channel",
    "description": "Return a structured classification for a YouTube channel.",
    "input_schema": {
        "type": "object",
        "properties": {
            "primary_category":  {"type": "string", "enum": _PRIMARY_CATEGORIES},
            "secondary_category": {"type": "string", "description": "Sub-category (empty string if none)"},
            "political_lean":    {"type": "string", "enum": _POLITICAL_LEANS},
            "content_domains":   {"type": "array",  "items": {"type": "string"},
                                  "description": "Topic domains e.g. ['politics', 'finance']"},
            "tone_style":        {"type": "string", "enum": _TONE_STYLES},
            "risk_white_supremacy":          {"type": "boolean"},
            "risk_ethnonationalism":         {"type": "boolean"},
            "risk_anti_immigrant_extremism": {"type": "boolean"},
            "risk_antisemitism":             {"type": "boolean"},
            "risk_anti_black_rhetoric":      {"type": "boolean"},
            "risk_anti_lgbtq_extremism":     {"type": "boolean"},
            "risk_religious_extremism":      {"type": "boolean"},
            "risk_conspiracy_driven":        {"type": "boolean"},
            "risk_harassment_mobs":          {"type": "boolean"},
            "risk_misinformation_pattern":   {"type": "boolean"},
            "notes": {"type": "string", "description": "Brief factual notes (empty string if none)"},
        },
        "required": [
            "primary_category", "secondary_category", "political_lean",
            "content_domains", "tone_style",
            "risk_white_supremacy", "risk_ethnonationalism",
            "risk_anti_immigrant_extremism", "risk_antisemitism",
            "risk_anti_black_rhetoric", "risk_anti_lgbtq_extremism",
            "risk_religious_extremism", "risk_conspiracy_driven",
            "risk_harassment_mobs", "risk_misinformation_pattern",
            "notes",
        ],
    },
}


# ── Classifier class ──────────────────────────────────────────────────────────

class LLMClassifier:
    """Classify unknown channels via the Anthropic API; cache results locally."""

    def __init__(self, cache_path: Path, model: str = "claude-haiku-4-5") -> None:
        self._cache_path = cache_path
        self._model = model
        self._client = anthropic.Anthropic()
        self._cache: Dict[str, Dict] = self._load_cache()
        self._dirty = False

    # ── Cache persistence ─────────────────────────────────────────────────────

    def _load_cache(self) -> Dict[str, Dict]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text()).get("channels", {})
            except (json.JSONDecodeError, KeyError, OSError):
                return {}
        return {}

    def flush(self) -> None:
        """Write cache to disk if it has unsaved entries."""
        if not self._dirty:
            return
        payload = {
            "_meta": {
                "description": "LLM classification cache. Keyed by channel_id.",
                "model": self._model,
                "updated": str(date.today()),
            },
            "channels": self._cache,
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(payload, indent=2))
        self._dirty = False

    def cache_hit(self, channel_id: str) -> bool:
        return channel_id in self._cache

    # ── Public classify ───────────────────────────────────────────────────────

    def classify(
        self, channel_id: str, channel_title: str, channel_url: str
    ) -> Dict[str, Any]:
        if channel_id in self._cache:
            return self._build_row(self._cache[channel_id])

        raw = self._call_api(channel_title, channel_url)
        raw["_model"] = self._model
        raw["_cached_at"] = str(date.today())
        self._cache[channel_id] = raw
        self._dirty = True
        return self._build_row(raw)

    # ── API call ──────────────────────────────────────────────────────────────

    def _call_api(self, channel_title: str, channel_url: str) -> Dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=[_CLASSIFY_TOOL],
            tool_choice={"type": "tool", "name": "classify_channel"},
            messages=[{
                "role": "user",
                "content": (
                    f"Channel title: {channel_title}\n"
                    f"Channel URL:   {channel_url}"
                ),
            }],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "classify_channel":
                return dict(block.input)
        raise ValueError(f"No tool_use block in API response for: {channel_title!r}")

    # ── Row builder ───────────────────────────────────────────────────────────

    def _build_row(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        risk_cols: Dict[str, bool] = {}
        for col in RISK_FLAG_COLUMNS:
            risk_cols[col] = bool(raw.get(col, False))

        domains = raw.get("content_domains", [])
        domains_str = json.dumps(domains) if isinstance(domains, list) else "[]"

        return {
            "primary_category":  raw.get("primary_category", "Unknown"),
            "secondary_category": raw.get("secondary_category", ""),
            "political_lean":    raw.get("political_lean", "unknown"),
            "content_domains":   domains_str,
            "tone_style":        raw.get("tone_style", "unknown"),
            **risk_cols,
            "risk_score":        sum(risk_cols.values()),
            "notes":             raw.get("notes", ""),
            "tone_shift_detected": False,
            "tone_shift_date":   "",
            "tone_shift_from":   "",
            "tone_shift_to":     "",
            "tone_shift_notes":  "",
            "enrichment_version": ENRICHMENT_VERSION,
            "enrichment_source": "llm",
        }
