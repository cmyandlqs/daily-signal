from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"spm", "from", "feature", "ref"}


def normalize_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith(TRACKING_PREFIXES) or key_lower in TRACKING_KEYS:
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items))
    normalized = parsed._replace(scheme=scheme, netloc=netloc, query=query, fragment="")
    return urlunparse(normalized)

