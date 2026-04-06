from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from app.fetcher.url_normalizer import normalize_url


@dataclass
class FetchedEntry:
    title: str
    url: str
    canonical_url: str
    content_raw: str
    published_at: datetime
    popularity: float


def _to_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def fetch_rss(url: str) -> list[FetchedEntry]:
    parsed = feedparser.parse(url)
    if parsed.bozo and not parsed.entries:
        return []

    entries: list[FetchedEntry] = []
    for item in parsed.entries:
        title = (getattr(item, "title", "") or "").strip()
        link = (getattr(item, "link", "") or "").strip()
        if not title or not link:
            continue
        summary = (
            getattr(item, "summary", None)
            or getattr(item, "description", None)
            or getattr(item, "content", None)
            or ""
        )
        if isinstance(summary, list) and summary:
            summary = summary[0].get("value", "")
        published_raw = getattr(item, "published", None) or getattr(item, "updated", None)
        entries.append(
            FetchedEntry(
                title=title,
                url=link,
                canonical_url=normalize_url(link),
                content_raw=str(summary),
                published_at=_to_datetime(published_raw),
                popularity=0.0,
            )
        )
    return entries

