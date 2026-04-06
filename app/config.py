from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class SlotConfig(BaseModel):
    name: str
    time: str


class ScheduleConfig(BaseModel):
    timezone: str = "Asia/Shanghai"
    slots: list[SlotConfig] = Field(default_factory=list)
    compensate_on_startup: bool = True


class SourceConfig(BaseModel):
    name: str
    platform: str
    rss_url: str
    enabled: bool = True
    source_weight: float = 0.5


class SemanticFilterConfig(BaseModel):
    enabled: bool = False
    similarity_threshold: float = 0.4


class FilterConfig(BaseModel):
    blacklist_keywords: list[str] = Field(default_factory=list)
    blacklist_domains: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    min_content_length: int = 50
    score_threshold: float = 0.3
    semantic_filter: SemanticFilterConfig = Field(default_factory=SemanticFilterConfig)


class SummarizerConfig(BaseModel):
    enabled: bool = False
    provider: str = "fallback"
    api_key: str | None = None
    model: str | None = None
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    request_timeout_seconds: int = 30
    top_n: int = 30
    max_tokens: int = 500


class PushConfig(BaseModel):
    enabled: bool = False
    provider: str = "serverchan"
    serverchan_key: str | None = None
    pushplus_token: str | None = None
    top_n: int = 5


class OutputConfig(BaseModel):
    dir: str = "./output"


class AppConfig(BaseModel):
    schedule: ScheduleConfig
    sources: list[SourceConfig]
    filters: FilterConfig = Field(default_factory=FilterConfig)
    summarizer: SummarizerConfig = Field(default_factory=SummarizerConfig)
    push: PushConfig = Field(default_factory=PushConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    database_url: str = "sqlite:///./data/daily_signal.db"


def _substitute_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), value)
    return value


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    hydrated = _substitute_env(raw)
    cfg = AppConfig(**hydrated)
    Path(cfg.output.dir).mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)
    return cfg
