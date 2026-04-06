from __future__ import annotations

from dataclasses import dataclass

from app.models import Entry


@dataclass
class Summary:
    one_liner: str
    bullets: list[str]
    why_it_matters: str
    tags: list[str]


class Summarizer:
    def summarize(self, entry: Entry) -> Summary:
        raise NotImplementedError

