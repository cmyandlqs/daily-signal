from __future__ import annotations

import json

import httpx

from app.config import SummarizerConfig
from app.models import Entry
from app.summarizer.base import Summarizer, Summary

PROMPT = """你是技术资讯编辑。基于输入内容生成中文摘要，禁止编造。\n输出 JSON，字段：one_liner, bullets, why_it_matters, tags。"""


class QwenOpenAISummarizer(Summarizer):
    def __init__(self, cfg: SummarizerConfig) -> None:
        if not cfg.api_key:
            raise ValueError("summarizer.api_key is required when provider=qwen_openai")
        self.cfg = cfg

    def summarize(self, entry: Entry) -> Summary:
        payload = {
            "model": self.cfg.model or "qwen-max",
            "messages": [
                {"role": "system", "content": PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"标题: {entry.title}\n"
                        f"正文: {entry.content_raw[:4000]}\n"
                        "请仅输出 JSON，不要额外说明。"
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": self.cfg.max_tokens,
            "response_format": {"type": "json_object"},
        }

        base = self.cfg.base_url.rstrip("/")
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.cfg.request_timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return Summary(
            one_liner=str(parsed.get("one_liner") or "信息不足"),
            bullets=[str(x) for x in parsed.get("bullets", [])][:3] or ["信息不足"],
            why_it_matters=str(parsed.get("why_it_matters") or "信息不足"),
            tags=[str(x) for x in parsed.get("tags", [])][:5],
        )

