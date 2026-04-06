# RSS 日报系统设计文档

## 概述

订阅推特（X）、知乎、B站、微博、GitHub Trending 等信息源，通过 RSSHub 抓取内容，经筛选与摘要后，按固定时段生成本地 Markdown 日报。

当前阶段目标：
- 固定时段运行：08:00 / 17:00
- 产出双文件：同一天在同一目录下生成 `YYYY-MM-DD-AM.md` 和 `YYYY-MM-DD-PM.md`
- 微信推送仅保留接口，不进入当前主流程

## 技术选型

| 组件 | 选择 |
|------|------|
| 后端 | FastAPI（可选，主要用于管理界面） |
| 数据库 | SQLite + SQLAlchemy |
| 定时 | APScheduler |
| 信息源抓取 | RSSHub + feedparser |
| Markdown 生成 | Jinja2（模板） |
| LLM 摘要 | 可配置（DeepSeek / 通义千问 / GLM） |
| 推送接口（预留） | Server酱 / PushPlus |

## 数据模型

### sources（订阅源配置）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| name | 源名称，如 "知乎热榜" |
| platform | 平台标识：zhihu / bilibili / weibo / twitter / github |
| rss_url | RSSHub 地址 |
| enabled | 是否启用 |
| source_weight | 来源权重 0-1（参与打分） |
| created_at | 创建时间 |

### entries（内容条目）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| source_id | 外键 → sources |
| title | 标题 |
| url | 原文链接 |
| canonical_url | 规范化链接（去跟踪参数） |
| title_fingerprint | 标题指纹（去重） |
| content_raw | 原始正文/描述 |
| published_at | 发布时间 |
| score | 综合总分 S |
| keyword_score | 关键词匹配分 |
| popularity_score | 热度分 |
| recency_score | 时效分 |
| one_liner | AI 摘要：一句话结论 |
| bullets_json | AI 摘要：要点 JSON |
| why_it_matters | AI 摘要：为什么值得看 |
| tags_json | 标签 JSON |
| status | raw / filtered / summarized / reported |
| created_at | 入库时间 |

约束建议：
- 唯一键：`(source_id, canonical_url)`
- 辅助去重：`title_fingerprint + published_at(小时粒度)`

### reports（每日报告）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| date | 日期（YYYY-MM-DD） |
| slot | 时段：AM / PM |
| file_path | Markdown 文件路径 |
| entry_count | 入选条目数 |
| summary_fail_count | 摘要失败数 |
| status | pending / done / failed |
| generated_at | 生成时间 |

约束建议：
- 唯一键：`(date, slot)`

## 内容处理管线

```
抓取 → 硬过滤 → 打分排序 → 语义复筛(可选) → AI摘要 → Markdown生成
```

### 1. 抓取层（fetcher）

- 通过 feedparser 拉取 RSSHub 各源
- 每次定时任务触发时，拉取所有启用 sources
- 提取 title、url、description/content、published_at、热度指标（如有）
- 先做 URL 规范化，再入库

### 2. 硬过滤（hard_filter）

- 去重：canonical_url 去重 + 标题指纹辅助去重
- 时效过滤：AM 报取最近 12h，PM 报取最近 9h（可配）
- 黑名单过滤：标题命中黑名单词 / 来源域名在黑名单中即丢弃
- 长度阈值：正文 < 50 字且无额外元数据即丢弃

### 3. 打分排序（scorer）

```
S = 0.35 * keyword_score
  + 0.25 * source_weight
  + 0.20 * popularity_score
  + 0.20 * recency_score
```

- keyword_score：标题+正文命中关键词列表，权重累加，归一化到 0-1
- source_weight：直接取 sources 表配置值
- popularity_score：按平台分别归一化；缺失热度时降权处理（不使用固定 0.5）
- recency_score：指数衰减，越新越高
- 低于阈值（默认 0.3）跳过，剩余按 S 降序

### 4. 语义复筛（semantic_filter，可选）

- 调用 embedding API（如 bge-m3）计算「内容 vs 用户主题描述」余弦相似度
- 相似度低于阈值（默认 0.4）剔除
- `config.yaml > filters.semantic_filter.enabled` 控制开关

### 5. AI 摘要（summarizer）

- 仅对 Top N（默认 30 条）调用 LLM
- 固定 prompt 模板，输出 JSON：

```json
{
  "one_liner": "一句话结论",
  "bullets": ["要点1", "要点2"],
  "why_it_matters": "为什么值得看",
  "tags": ["tag1", "tag2"]
}
```

- LLM 调用失败时降级：正文前 100 字截断，`summary_fail_count++`

## 调度与可靠性

这是本地定时任务的典型问题，解决方案是“补偿执行”。

- 固定时段：每天 `08:00` 与 `17:00`
- 开机自检：程序启动时检查当天 AM/PM 是否已执行；缺失则立即补跑
- 状态持久化：将每个时段的 `last_run_at`、`date+slot` 写入 SQLite（或 state.json）
- 幂等控制：同一 `date+slot` 重复触发只允许一次成功写报告

结论：`定时触发 + 开机补偿 + 状态持久化 + 幂等控制`

## Markdown 生成

输出目录：`output/`

文件规则：
- 早报：`output/YYYY-MM-DD-AM.md`
- 晚报：`output/YYYY-MM-DD-PM.md`

内容规则：
- 按平台分组，每组按分数降序
- 每条格式：标题 → 来源/热度/分数 → 要点 → 为什么值得看 → 标签 → 原文链接

## 微信推送（接口预留）

当前阶段不启用主动推送，仅保留接口层：
- `pusher/serverchan.py`
- `pusher/pushplus.py`

启用时要求：
- 推送失败不阻塞主流程
- 默认只推 Top N 精简内容

## Web 界面（可选）

当前阶段可只保留最小页面：
- `/reports`：报告列表
- `/reports/:date/:slot`：在线查看指定 AM/PM 报告
- `/logs`：运行日志

## 项目结构

```text
RSS_information/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── fetcher/
│   │   ├── rss_client.py
│   │   └── url_normalizer.py
│   ├── filter/
│   │   ├── hard_filter.py
│   │   ├── scorer.py
│   │   └── semantic_filter.py
│   ├── summarizer/
│   │   ├── base.py
│   │   ├── deepseek.py
│   │   ├── qianwen.py
│   │   ├── glm.py
│   │   └── fallback.py
│   ├── generator/
│   │   └── markdown_builder.py
│   ├── pusher/                # 接口预留，当前不启用
│   │   ├── serverchan.py
│   │   └── pushplus.py
│   ├── scheduler/
│   │   └── jobs.py
│   └── pipeline.py
├── config.yaml
├── run.py
├── output/
└── data/
```

## 配置文件（config.yaml）

```yaml
schedule:
  timezone: "Asia/Shanghai"
  slots:
    - name: "AM"
      time: "08:00"
    - name: "PM"
      time: "17:00"
  compensate_on_startup: true

sources:
  - name: "知乎热榜"
    platform: "zhihu"
    rss_url: "https://rsshub.app/zhihu/hotlist"
    enabled: true
    source_weight: 0.8
  - name: "GitHub Trending"
    platform: "github"
    rss_url: "https://rsshub.app/github/trending/daily"
    enabled: true
    source_weight: 0.9
  # ... twitter / bilibili / weibo 等

filters:
  blacklist_keywords: ["广告", "推广"]
  blacklist_domains: []
  min_content_length: 50
  score_threshold: 0.3
  semantic_filter:
    enabled: false
    similarity_threshold: 0.4

summarizer:
  provider: "deepseek"
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-chat"
  top_n: 30
  max_tokens: 500

push:
  enabled: false
  provider: "serverchan"
  serverchan_key: "${SERVERCHAN_KEY}"
  pushplus_token: "${PUSHPLUS_TOKEN}"
  top_n: 5

output:
  dir: "./output"
```

## 落地节奏

| 阶段 | 内容 | 依赖 |
|------|------|------|
| P0 | 抓取 + 硬过滤 + 非LLM摘要（截断）+ 双文件Markdown生成 + 定时补偿执行 | 无外部API |
| P1 | 打分排序 + LLM摘要 | LLM API |
| P2 | 语义复筛 + 可选Web完善 + 可选推送启用 | Embedding API / 推送Key |
