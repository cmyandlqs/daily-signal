from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import feedparser
import httpx
import yaml


@dataclass
class SourceCheckResult:
    name: str
    platform: str
    url: str
    status_code: int | None
    ok_http: bool
    ok_feed: bool
    entry_count: int
    error: str


def load_sources(config_path: Path) -> list[dict]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("config.yaml 中的 sources 必须是列表")
    return sources


def check_source(client: httpx.Client, source: dict) -> SourceCheckResult:
    name = str(source.get("name", "unknown"))
    platform = str(source.get("platform", "unknown"))
    url = str(source.get("rss_url", "")).strip()
    enabled = bool(source.get("enabled", True))

    if not enabled:
        return SourceCheckResult(
            name=name,
            platform=platform,
            url=url,
            status_code=None,
            ok_http=True,
            ok_feed=True,
            entry_count=0,
            error="disabled",
        )

    if not url:
        return SourceCheckResult(
            name=name,
            platform=platform,
            url=url,
            status_code=None,
            ok_http=False,
            ok_feed=False,
            entry_count=0,
            error="empty rss_url",
        )

    status_code: int | None = None
    ok_http = False
    ok_feed = False
    entry_count = 0
    error = ""

    try:
        resp = client.get(url, follow_redirects=True)
        status_code = resp.status_code
        ok_http = resp.status_code == 200
        content = resp.content
        parsed = feedparser.parse(content)
        entry_count = len(parsed.entries or [])
        ok_feed = not bool(getattr(parsed, "bozo", 0))
        if not ok_feed:
            exc = getattr(parsed, "bozo_exception", None)
            error = f"feed parse error: {exc}"
        if ok_http and not ok_feed and entry_count > 0:
            # Some feeds are parseable with bozo warnings; treat as soft success.
            ok_feed = True
            error = ""
        if not ok_http:
            error = f"http status={resp.status_code}; body={resp.text[:160].replace(chr(10), ' ')}"
    except Exception as exc:
        error = f"request error: {exc}"

    return SourceCheckResult(
        name=name,
        platform=platform,
        url=url,
        status_code=status_code,
        ok_http=ok_http,
        ok_feed=ok_feed,
        entry_count=entry_count,
        error=error,
    )


def print_report(results: list[SourceCheckResult]) -> None:
    print("=== Source Availability Report ===")
    print(f"total={len(results)}")
    print("")
    for idx, r in enumerate(results, start=1):
        state = "PASS" if (r.ok_http and r.ok_feed) else "FAIL"
        print(f"[{idx:02d}] {state} | {r.name} ({r.platform})")
        print(f"     url={r.url}")
        print(
            f"     http={r.status_code if r.status_code is not None else '-'} "
            f"ok_http={r.ok_http} ok_feed={r.ok_feed} entries={r.entry_count}"
        )
        if r.error:
            print(f"     error={r.error}")
    print("")

    passed = sum(1 for r in results if r.ok_http and r.ok_feed)
    failed = len(results) - passed
    print(f"summary: pass={passed} fail={failed}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check availability of all RSS sources in config.yaml")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP request timeout in seconds")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config file not found: {config_path}")
        return 2

    try:
        sources = load_sources(config_path)
    except Exception as exc:
        print(f"failed to load sources: {exc}")
        return 2

    results: list[SourceCheckResult] = []
    with httpx.Client(timeout=args.timeout, headers={"User-Agent": "daily-signal-source-check/0.1"}) as client:
        for source in sources:
            results.append(check_source(client, source))

    print_report(results)

    has_failure = any(not (r.ok_http and r.ok_feed) for r in results if r.error != "disabled")
    return 1 if has_failure else 0


if __name__ == "__main__":
    sys.exit(main())

