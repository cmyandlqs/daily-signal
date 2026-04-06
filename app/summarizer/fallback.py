from __future__ import annotations

from app.models import Entry
from app.summarizer.base import Summarizer, Summary


class FallbackSummarizer(Summarizer):
    def summarize(self, entry: Entry) -> Summary:
        snippet = " ".join((entry.content_raw or "").split())
        snippet = snippet[:100] if snippet else "信息不足"
        return Summary(
            one_liner=snippet,
            bullets=[snippet],
            why_it_matters="提供快速浏览，帮助判断是否值得阅读全文。",
            tags=[entry.source.platform],
        )

