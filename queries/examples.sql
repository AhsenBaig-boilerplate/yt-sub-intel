-- yt-sub-intel: Example DuckDB queries
-- Run via: duckdb -c ".read queries/examples.sql"
-- Or interactively: duckdb  →  .read queries/examples.sql

-- ─── Setup ──────────────────────────────────────────────────────────────────

-- Load the enriched Parquet once and query repeatedly
CREATE OR REPLACE VIEW subs AS
SELECT * FROM read_parquet('output/subscriptions_enriched.parquet');


-- ─── Overview ───────────────────────────────────────────────────────────────

-- Total channels by status
SELECT status, COUNT(*) AS count
FROM subs
GROUP BY status
ORDER BY count DESC;

-- Breakdown by primary category
SELECT primary_category, COUNT(*) AS count
FROM subs
WHERE status = 'active'
GROUP BY primary_category
ORDER BY count DESC;

-- Breakdown by political lean
SELECT political_lean, COUNT(*) AS count
FROM subs
WHERE status = 'active'
GROUP BY political_lean
ORDER BY count DESC;


-- ─── Risk Analysis ──────────────────────────────────────────────────────────

-- All channels with any risk flag set
SELECT channel_title, primary_category, political_lean, risk_score, notes
FROM subs
WHERE risk_score > 0
ORDER BY risk_score DESC, channel_title;

-- Risk flag breakdown (how many channels have each flag)
SELECT
    SUM(risk_white_supremacy::INT)          AS white_supremacy,
    SUM(risk_ethnonationalism::INT)         AS ethnonationalism,
    SUM(risk_anti_immigrant_extremism::INT) AS anti_immigrant_extremism,
    SUM(risk_antisemitism::INT)             AS antisemitism,
    SUM(risk_anti_black_rhetoric::INT)      AS anti_black_rhetoric,
    SUM(risk_anti_lgbtq_extremism::INT)     AS anti_lgbtq_extremism,
    SUM(risk_religious_extremism::INT)      AS religious_extremism,
    SUM(risk_conspiracy_driven::INT)        AS conspiracy_driven,
    SUM(risk_harassment_mobs::INT)          AS harassment_mobs,
    SUM(risk_misinformation_pattern::INT)   AS misinformation_pattern
FROM subs
WHERE status = 'active';

-- High-risk channels (2+ flags)
SELECT channel_title, political_lean, risk_score,
       risk_white_supremacy, risk_ethnonationalism, risk_conspiracy_driven,
       risk_misinformation_pattern, notes
FROM subs
WHERE risk_score >= 2 AND status = 'active'
ORDER BY risk_score DESC;


-- ─── Political Lean Distribution ────────────────────────────────────────────

-- Proportion of subscriptions by lean
SELECT
    political_lean,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM subs
WHERE status = 'active'
GROUP BY political_lean
ORDER BY count DESC;

-- Far-right channels specifically
SELECT channel_title, primary_category, secondary_category, tone_style, risk_score
FROM subs
WHERE political_lean IN ('far_right', 'right') AND status = 'active'
ORDER BY risk_score DESC, channel_title;


-- ─── Tone Shifts ────────────────────────────────────────────────────────────

-- Channels with detected tone shifts
SELECT channel_title, tone_shift_date, tone_shift_from, tone_shift_to, tone_shift_notes
FROM subs
WHERE tone_shift_detected = true
ORDER BY tone_shift_date DESC;


-- ─── Temporal Tracking ──────────────────────────────────────────────────────

-- Channels added most recently (new in latest import)
SELECT channel_title, primary_category, political_lean, first_seen_date
FROM subs
ORDER BY first_seen_date DESC
LIMIT 20;

-- Channels that have been removed since initial import
SELECT channel_title, primary_category, last_seen_date
FROM subs
WHERE status = 'removed'
ORDER BY last_seen_date DESC;


-- ─── Enrichment Quality ─────────────────────────────────────────────────────

-- How was each channel classified?
SELECT enrichment_source, COUNT(*) AS count
FROM subs
WHERE status = 'active'
GROUP BY enrichment_source
ORDER BY count DESC;

-- Channels that fell through to "default" classification (need manual review)
SELECT channel_id, channel_title, channel_url
FROM subs
WHERE enrichment_source = 'default' AND status = 'active'
ORDER BY channel_title;
