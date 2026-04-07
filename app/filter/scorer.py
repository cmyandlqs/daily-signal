from __future__ import annotations

import math
from datetime import datetime

from app.config import FilterConfig
from app.models import Entry, Source


def _keyword_score(entry: Entry, include_keywords: list[str]) -> float:
    if not include_keywords:
        return 0.5
    text = f"{entry.title}\n{entry.content_raw}".lower()
    hits = sum(1 for kw in include_keywords if kw.lower() in text)
    return min(1.0, hits / max(1, len(include_keywords)))


def _recency_score(entry: Entry, now: datetime) -> float:
    age_hours = max(0.0, (now - entry.published_at).total_seconds() / 3600.0)
    return math.exp(-age_hours / 24.0)


def score_entries(
    entries: list[Entry],
    source_map: dict[int, Source],
    filter_cfg: FilterConfig,
    now: datetime,
) -> list[Entry]:
    scored: list[Entry] = []
    for entry in entries:
        source = source_map[entry.source_id]
        entry.keyword_score = _keyword_score(entry, filter_cfg.include_keywords)
        entry.popularity_score = 0.0
        entry.recency_score = _recency_score(entry, now)
        entry.score = (
            0.35 * entry.keyword_score
            + 0.25 * source.source_weight
            + 0.20 * entry.popularity_score
            + 0.20 * entry.recency_score
        )
        if entry.score >= filter_cfg.score_threshold:
            scored.append(entry)

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def cap_entries_per_source(entries: list[Entry], max_items_per_source: int) -> list[Entry]:
    if max_items_per_source <= 0:
        return entries

    kept: list[Entry] = []
    source_counter: dict[int, int] = {}
    for entry in entries:
        count = source_counter.get(entry.source_id, 0)
        if count >= max_items_per_source:
            continue
        kept.append(entry)
        source_counter[entry.source_id] = count + 1
    return kept
