from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from jinja2 import Template

from app.models import Entry

REPORT_TEMPLATE = Template(
    """# Daily Signal {{ date }} {{ slot }}

{% for platform, items in grouped.items() %}
## {{ platform }}
{% for e in items %}
- [{{ e.title }}]({{ e.url }})
  - score: {{ '%.3f'|format(e.score) }}
  - one_liner: {{ e.one_liner }}
  - bullets: {% for b in e.bullets %}{{ b }}{% if not loop.last %} | {% endif %}{% endfor %}
  - why_it_matters: {{ e.why_it_matters }}
{% endfor %}
{% endfor %}
"""
)


def build_markdown_report(entries: list[Entry], output_dir: str, date: str, slot: str) -> str:
    grouped_raw: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped_raw[entry.source.platform].append(entry)

    grouped_render = {}
    for platform, items in grouped_raw.items():
        grouped_render[platform] = []
        for item in items:
            try:
                bullets = json.loads(item.bullets_json or "[]")
            except json.JSONDecodeError:
                bullets = []
            grouped_render[platform].append(
                {
                    "title": item.title,
                    "url": item.url,
                    "score": item.score,
                    "one_liner": item.one_liner,
                    "bullets": bullets,
                    "why_it_matters": item.why_it_matters,
                }
            )

    content = REPORT_TEMPLATE.render(date=date, slot=slot, grouped=grouped_render)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    report_path = Path(output_dir) / f"{date}-{slot}.md"
    report_path.write_text(content, encoding="utf-8")
    return str(report_path)

