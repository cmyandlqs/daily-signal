# daily-signal

[English](./README_EN.md) | 简体中文

一个本地定时信息简报工具：抓取多源 RSS/Atom，筛选后生成 Markdown 日报（AM/PM 双文件）。

## 功能

- 多源订阅（`config.yaml` 配置）
- 定时任务（固定 `08:00` / `17:00`）
- 补偿执行（错过时段可补跑）
- 内容过滤与评分
- LLM 摘要（可选，支持 `qwen3.5-flash` OpenAI 兼容接口）
- 输出 Markdown 文件：
  - `output/YYYY-MM-DD-AM.md`
  - `output/YYYY-MM-DD-PM.md`

## 环境要求

- Python 3.11+
- Windows（当前优先验证），Ubuntu 可迁移运行

安装依赖：

```powershell
uv pip install -r requirements.txt
```

## 配置

### 1. 编辑 `config.yaml`

- `sources`：配置启用的信息源
- `schedule`：固定时段与补偿开关
- `filters`：黑名单、长度阈值、分数阈值
- `summarizer`：是否启用 LLM 摘要

### 2. 配置 `.env`（可选）

如果启用 qwen 摘要：

```env
DASHSCOPE_API_KEY=你的Key
```

## 快速开始

### 1. 初始化数据库

```powershell
.\.venv\Scripts\python.exe run.py init-db
```

### 2. 单次生成报告

```powershell
.\.venv\Scripts\python.exe run.py once --slot AM
.\.venv\Scripts\python.exe run.py once --slot PM
```

如果当天该时段已生成，默认会跳过；强制重跑：

```powershell
.\.venv\Scripts\python.exe run.py once --slot AM --force
.\.venv\Scripts\python.exe run.py once --slot PM --force
```

### 3. 启动定时常驻

```powershell
.\.venv\Scripts\python.exe run.py schedule
```

## 源可用性测试

测试 `config.yaml` 中全部源：

```powershell
.\.venv\Scripts\python.exe scripts\test_sources_availability.py --config config.yaml --timeout 20
```

## 日志与输出

- 日志文件：`logs/app.log`
- 报告目录：`output/`
- 数据库：`data/daily_signal.db`

## 常见说明

- `rsshub.app` 公共实例可能限流/403，建议替换为可用源或后续自建 RSSHub。
- LLM 调用失败会自动降级，不阻塞报告生成。
- 过滤后 `kept=0` 通常是窗口、阈值或过滤条件过严导致，可调整 `config.yaml`。

