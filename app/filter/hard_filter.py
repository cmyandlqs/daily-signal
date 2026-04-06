from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from app.config import FilterConfig
from app.models import Entry


@dataclass
class FilterResult:
    kept: list[Entry]
    dropped_by_reason: dict[str, int]


def make_title_fingerprint(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def apply_hard_filter(
    entries: list[Entry],
    filter_cfg: FilterConfig,
    window_start: datetime,
    window_end: datetime,
) -> FilterResult:
    kept: list[Entry] = []
    reasons: dict[str, int] = {}
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for entry in entries:
        if entry.canonical_url in seen_urls:
            reasons["duplicate_url"] = reasons.get("duplicate_url", 0) + 1
            continue
        if entry.title_fingerprint in seen_titles:
            reasons["duplicate_title"] = reasons.get("duplicate_title", 0) + 1
            continue

        if not (window_start <= entry.published_at <= window_end):
            reasons["out_of_window"] = reasons.get("out_of_window", 0) + 1
            continue

        title_lower = entry.title.lower()
        if any(word.lower() in title_lower for word in filter_cfg.blacklist_keywords):
            reasons["blacklist_keyword"] = reasons.get("blacklist_keyword", 0) + 1
            continue

        domain = urlparse(entry.canonical_url).netloc.lower()
        if domain and any(domain.endswith(d.lower()) for d in filter_cfg.blacklist_domains):
            reasons["blacklist_domain"] = reasons.get("blacklist_domain", 0) + 1
            continue

        if len((entry.content_raw or "").strip()) < filter_cfg.min_content_length:
            reasons["content_too_short"] = reasons.get("content_too_short", 0) + 1
            continue

        seen_urls.add(entry.canonical_url)
        seen_titles.add(entry.title_fingerprint)
        kept.append(entry)

    return FilterResult(kept=kept, dropped_by_reason=reasons)

