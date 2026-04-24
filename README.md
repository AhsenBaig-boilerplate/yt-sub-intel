# yt-sub-intel

**YouTube Subscription Intelligence** — a repeatable pipeline for enriching YouTube subscription exports with categories, political lean, risk flags, and change tracking.

---

## Overview

Google Takeout gives you a raw CSV of your YouTube subscriptions. This pipeline enriches each channel with:

| Field group | What it adds |
| --- | --- |
| **Categories** | `primary_category`, `secondary_category` |
| **Editorial lean** | `political_lean` (far_left → far_right → nonpartisan) |
| **Content signals** | `content_domains`, `tone_style` |
| **Risk flags** | 10 boolean flags (white supremacy, conspiracy, misinformation, etc.) + `risk_score` |
| **Tone shifts** | Metadata when a channel's editorial direction has visibly changed |
| **Lifecycle tracking** | `first_seen_date`, `last_seen_date`, `status` (active / removed) |

Output is a **Parquet file** (canonical store) + **CSV** (human-readable). Repeated imports diff against the previous run and report new / removed / modified channels.

---

## Project Structure

```text
yt-sub-intel/
├── data/
│   └── subscriptions_raw.csv          ← place Google Takeout export here
├── output/
│   ├── subscriptions_enriched.csv     ← generated
│   ├── subscriptions_enriched.parquet ← generated (canonical)
│   └── diff_report.json               ← generated on re-import
├── yt_sub_intel/
│   ├── schema.py                      ← Polars schema + field constants
│   ├── classifier.py                  ← classification engine
│   ├── diff.py                        ← change detection
│   ├── enricher.py                    ← main pipeline
│   └── cli.py                         ← Click CLI entry point
├── mappings/
│   ├── channel_classifications.json   ← manual channel-level overrides
│   └── keyword_rules.json             ← regex rules for auto-classification
├── dashboard/
│   └── index.html                     ← DuckDB-WASM browser dashboard
├── schema/
│   └── enriched_schema.json           ← JSON Schema for all fields
├── queries/
│   └── examples.sql                   ← DuckDB analytics queries
├── enrich.py                          ← convenience wrapper (prefer yt-sub-intel CLI)
└── pyproject.toml
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .            # installs the yt-sub-intel CLI
```

Or without a venv:

```bash
pip install -r requirements.txt
```

---

## Getting Your Subscriptions Export

1. Go to [Google Takeout](https://takeout.google.com/)
2. Deselect all, then select **YouTube and YouTube Music**
3. Under YouTube, select only **Subscriptions**
4. Export and download the zip
5. Extract and find `subscriptions.csv` inside `Takeout/YouTube and YouTube Music/subscriptions/`
6. Copy it to `data/subscriptions_raw.csv`

The expected CSV format is:

```csv
Channel Id,Channel Url,Channel Title
UCxxx,http://www.youtube.com/channel/UCxxx,Channel Name
```

---

## Running the Pipeline

**First import:**

```bash
yt-sub-intel
```

**Subsequent imports** (after getting a new Takeout export):

```bash
cp /path/to/new/subscriptions.csv data/subscriptions_raw.csv
yt-sub-intel
```

The pipeline will:

- Detect new channels (subscribed since last run)
- Detect removed channels (unsubscribed)
- Detect classification changes
- Merge everything into the canonical Parquet
- Print a diff summary

**Custom paths:**

```bash
yt-sub-intel --raw /path/to/subscriptions.csv --output /path/to/output/
```

---

## Dashboard

After running the pipeline, open the browser dashboard to explore your subscriptions visually:

```bash
# From the project root:
python -m http.server 8000
```

Then open <http://localhost:8000/dashboard/> in your browser.

The dashboard loads `output/subscriptions_enriched.parquet` via DuckDB-WASM and shows:

- Summary cards (active, flagged, high-risk, removed)
- Category and political lean breakdown charts
- Risk flag counts
- Searchable, sortable subscriptions table with color-coded risk badges

---

## Querying with DuckDB

**Interactive:**

```bash
duckdb
```

```sql
SELECT channel_title, political_lean, risk_score
FROM read_parquet('output/subscriptions_enriched.parquet')
WHERE risk_score > 0
ORDER BY risk_score DESC;
```

**Run example queries:**

```bash
duckdb -c ".read queries/examples.sql"
```

**Python:**

```python
import duckdb
con = duckdb.connect()
df = con.execute("SELECT * FROM read_parquet('output/subscriptions_enriched.parquet')").df()
```

---

## Classification System

Classification resolves in this order:

1. **Exact match by `channel_id`** in `mappings/channel_classifications.json`
2. **Exact match by `channel_title`** (case-insensitive) in the same file
3. **First matching regex rule** in `mappings/keyword_rules.json`
4. **Default** — `primary_category: "Unknown"`, `political_lean: "unknown"`

After a run, filter `enrichment_source = "default"` in the output to find channels that need manual classification.

### Adding a channel manually

Edit `mappings/channel_classifications.json` and add an entry:

```json
{
  "channel_id": "UCxxxxxx",
  "channel_title": "My Favorite Channel",
  "primary_category": "Science & Education",
  "secondary_category": "Physics",
  "political_lean": "nonpartisan",
  "content_domains": ["physics", "engineering"],
  "tone_style": "educational",
  "risk_flags": {},
  "notes": ""
}
```

Re-run `yt-sub-intel` to apply.

### Adding a keyword rule

Edit `mappings/keyword_rules.json`:

```json
{
  "id": "rule_my_pattern",
  "pattern": "(?i)\\b(pattern1|pattern2)\\b",
  "primary_category": "Technology",
  "secondary_category": "AI",
  "political_lean": "nonpartisan",
  "tone_style": "educational",
  "risk_flags": {}
}
```

Rules are applied in order — put more specific patterns first.

---

## Risk Flags

| Flag | What it captures |
| --- | --- |
| `risk_white_supremacy` | Explicit white supremacist content or affiliation |
| `risk_ethnonationalism` | Ethnic or racial nationalist ideology |
| `risk_anti_immigrant_extremism` | Extreme anti-immigration rhetoric |
| `risk_antisemitism` | Antisemitic content or conspiracy promotion |
| `risk_anti_black_rhetoric` | Anti-Black rhetoric or racist framing |
| `risk_anti_lgbtq_extremism` | Extreme anti-LGBTQ+ content |
| `risk_religious_extremism` | Religious extremism (any faith) |
| `risk_conspiracy_driven` | Primary content is conspiracy theories |
| `risk_harassment_mobs` | History of directing followers to harass individuals |
| `risk_misinformation_pattern` | Documented pattern of publishing misinformation |

`risk_score` = count of true flags (0–10). Channels with `risk_score >= 2` warrant close review.

---

## Parquet Schema

All output is written as [Snappy-compressed Parquet](https://parquet.apache.org/) — compatible with DuckDB, Pandas, Polars, Apache Spark, and any BI tool.

See `schema/enriched_schema.json` for the full JSON Schema definition.

---

## Extending the Pipeline

| Goal | Where to change |
| --- | --- |
| Add a new enrichment field | `yt_sub_intel/schema.py` → `POLARS_SCHEMA`, `yt_sub_intel/classifier.py` → `_build_row`, `schema/enriched_schema.json` |
| Add channel classifications | `mappings/channel_classifications.json` |
| Add auto-classification rules | `mappings/keyword_rules.json` |
| Add DuckDB analytics | `queries/examples.sql` |
| Change output location | `--output` flag or edit `DEFAULT_OUTPUT` in `yt_sub_intel/cli.py` |
| Add LLM-based enrichment | New classifier in `yt_sub_intel/classifier.py`, add `"llm"` to `enrichment_source` enum |

---

## Future Roadmap

- [ ] LLM-assisted auto-classification for unknown channels
- [ ] Channel growth / content velocity tracking
- [ ] Export to Obsidian / Notion
- [ ] `pipx install` packaging for global install without a venv
