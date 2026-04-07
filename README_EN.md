# daily-signal

A local scheduled daily briefing tool: fetches from multiple RSS/Atom sources, filters content, and generates Markdown daily reports (AM/PM dual files).

## Features

- Multi-source subscriptions (configured via `config.yaml`)
- Scheduled tasks (fixed at `08:00` / `17:00`)
- Catch-up execution (missed slots can be re-run)
- Content filtering and scoring
- LLM summarization (optional, supports `qwen3.5-flash` OpenAI-compatible API)
- Output Markdown files:
  - `output/YYYY-MM-DD-AM.md`
  - `output/YYYY-MM-DD-PM.md`

## Requirements

- Python 3.11+
- Windows (currently prioritized), Ubuntu is portable

Install dependencies:

```powershell
uv pip install -r requirements.txt
```

## Configuration

### 1. Edit `config.yaml`

- `sources`: Configure enabled information sources
- `schedule`: Fixed time slots and catch-up toggle
- `filters`: Blacklist, length threshold, score threshold
- `summarizer`: Enable/disable LLM summarization

### 2. Configure `.env` (Optional)

If enabling qwen summarization:

```env
DASHSCOPE_API_KEY=YourKey
```

## Quick Start

### 1. Initialize Database

```powershell
.\.venv\Scripts\python.exe run.py init-db
```

> **Note:** Only needs to be run once. See [FAQ](#faq).

### 2. Generate Report Once

```powershell
.\.venv\Scripts\python.exe run.py once --slot AM
.\.venv\Scripts\python.exe run.py once --slot PM
```

If the report for that day/slot already exists, it will be skipped by default. To force re-run:

```powershell
.\.venv\Scripts\python.exe run.py once --slot AM --force
.\.venv\Scripts\python.exe run.py once --slot PM --force
```

### 3. Start Scheduler Service

```powershell
.\.venv\Scripts\python.exe run.py schedule
```

## Source Availability Test

Test all sources in `config.yaml`:

```powershell
.\.venv\Scripts\python.exe scripts\test_sources_availability.py --config config.yaml --timeout 20
```

## Logs & Output

- Log files: `logs/app.log`
- Report directory: `output/`
- Database: `data/daily_signal.db`

## FAQ

### Do I need to run `init-db` every time?

**No.** The `init-db` command only needs to be run:
- **First time setup** — Creates database tables
- **After model changes** — When you modify `app/models.py` (add tables, add columns)

The operation is idempotent — if tables exist, it will skip them safely without affecting existing data.

### Common Issues

- **`rsshub.app` public instances may rate-limit/return 403** — Consider replacing with available sources or self-hosting RSSHub.
- **LLM API call failures** — Automatically degrades gracefully, won't block report generation.
- **`kept=0` after filtering** — Usually caused by overly strict window/threshold/filter settings, adjust `config.yaml`.
