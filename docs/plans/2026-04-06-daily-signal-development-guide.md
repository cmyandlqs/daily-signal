# daily-signal 详细开发文档（执行版）

## 1. 文档目标

本文件用于指导后续开发落地，目标是按固定时段（08:00/17:00）生成本地 Markdown 双文件日报：
- `output/YYYY-MM-DD-AM.md`
- `output/YYYY-MM-DD-PM.md`

当前范围：
- 必做：抓取、过滤、排序、摘要（可降级）、Markdown 生成、定时与补偿执行
- 预留：微信推送接口（不在当前主流程启用）

---

## 2. 开发原则

1. 先跑通主链路，再加智能能力
2. 先保证稳定性，再追求复杂功能
3. 所有任务都应可观测（日志、状态、错误原因）
4. 同一 `date+slot` 报告必须幂等

---

## 3. 里程碑与交付

### M1：可运行的基础日报（P0）

交付标准：
- 可从至少 2 个源抓取（建议：知乎热榜 + GitHub Trending）
- 可完成硬过滤和去重
- 可生成 AM/PM 双文件
- 支持固定时段调度 + 开机补偿执行
- 可在本地查看历史报告文件

### M2：质量提升（P1）

交付标准：
- 支持评分排序（score）
- 支持 LLM 摘要（Top N）
- 摘要失败有降级策略
- 报告内容结构稳定

### M3：增强能力（P2）

交付标准：
- 语义复筛（可开关）
- 简易 Web 查看/管理页（可选）
- 推送接口可独立调用（默认关闭）

---

## 4. 目录与模块职责

```text
RSS_information/
├── app/
│   ├── main.py                     # 应用入口（可选）
│   ├── config.py                   # 配置加载与校验
│   ├── database.py                 # DB 引擎与会话
│   ├── models.py                   # ORM 模型
│   ├── fetcher/
│   │   ├── rss_client.py           # RSS 拉取
│   │   └── url_normalizer.py       # URL 规范化
│   ├── filter/
│   │   ├── hard_filter.py          # 去重/时效/黑名单/长度过滤
│   │   ├── scorer.py               # 评分排序
│   │   └── semantic_filter.py      # 语义复筛（可选）
│   ├── summarizer/
│   │   ├── base.py                 # 摘要抽象接口
│   │   ├── deepseek.py             # 供应商适配
│   │   └── fallback.py             # 摘要失败降级
│   ├── generator/
│   │   └── markdown_builder.py     # 报告生成
│   ├── scheduler/
│   │   └── jobs.py                 # 定时任务与补偿逻辑
│   ├── pusher/
│   │   ├── serverchan.py           # 预留
│   │   └── pushplus.py             # 预留
│   └── pipeline.py                 # 主流程编排
├── config.yaml
├── run.py
├── output/
└── data/
```

---

## 5. 数据模型实施要点

### 5.1 sources

必须字段：
- `name`, `platform`, `rss_url`, `enabled`, `source_weight`

### 5.2 entries

必须字段：
- `source_id`, `title`, `url`, `canonical_url`, `title_fingerprint`, `content_raw`, `published_at`, `status`

建议字段：
- `score`, `keyword_score`, `popularity_score`, `recency_score`
- `one_liner`, `bullets_json`, `why_it_matters`, `tags_json`

约束：
- 唯一键：`(source_id, canonical_url)`

### 5.3 reports

必须字段：
- `date`, `slot`, `file_path`, `entry_count`, `summary_fail_count`, `status`, `generated_at`

约束：
- 唯一键：`(date, slot)`

---

## 6. 核心流程（必须按顺序落地）

1. 加载配置（`config.yaml` + `.env`）
2. 计算本次运行上下文（`date`, `slot`, 时间窗口）
3. 抓取启用源内容并入库（先规范化 URL）
4. 执行硬过滤（去重、时效、黑名单、长度）
5. 执行评分排序（可在 P1 开启）
6. 对 Top N 做摘要（失败则降级）
7. 渲染 Markdown 文件（AM/PM 双文件）
8. 写入 reports 状态与统计
9. 记录运行日志

---

## 7. 调度与补偿执行（重点）

### 固定时段
- AM：`08:00`
- PM：`17:00`

### 补偿执行

程序启动后立即执行自检：
1. 检查当天 `AM/PM` 是否已完成
2. 对缺失时段立即补跑
3. 更新 `last_run_at` 与 `reports(date, slot)`

### 幂等保障

- 若 `reports(date, slot)` 已 `done`，则跳过重复生成
- 若任务并发触发，使用进程锁或数据库锁保护同一 `date+slot`

---

## 8. 各模块开发任务清单

### 8.1 config.py

- 定义配置 Schema（Pydantic）
- 支持环境变量替换 `${VAR}`
- 启动时输出关键配置摘要（隐去密钥）

验收：配置缺项时报错清晰，可定位字段。

### 8.2 fetcher/rss_client.py

- 基于 feedparser 抓取并标准化结构
- 请求失败与解析失败分开记录
- 支持超时、重试、退避

验收：单源失败不影响其他源。

### 8.3 fetcher/url_normalizer.py

- 去 `utm_*`、`spm` 等追踪参数
- 统一协议、host 大小写

验收：同一内容不同追踪参数 URL 归一后相同。

### 8.4 filter/hard_filter.py

- URL 去重 + 标题指纹辅助去重
- 时效窗口过滤（按 AM/PM）
- 黑名单词、黑名单域名过滤
- 最小长度过滤

验收：过滤原因可统计输出。

### 8.5 filter/scorer.py

- 实现评分公式与阈值过滤
- 输出 `score_breakdown`

验收：同一批数据重复计算结果一致。

### 8.6 summarizer/

- 定义统一接口：`summarize(entry) -> summary_json`
- 实现 provider 适配（先 DeepSeek）
- 失败降级到截断摘要

验收：摘要失败不终止生成流程。

### 8.7 generator/markdown_builder.py

- 读取模板渲染报告
- 按平台分组、组内排序
- 写入 `output/YYYY-MM-DD-AM.md` 或 `...-PM.md`

验收：文件命名稳定、重复运行可覆盖同 slot 文件。

### 8.8 scheduler/jobs.py

- 建立 08:00/17:00 两个 job
- 启动时执行补偿检查
- 写入任务日志

验收：关机错过后，开机可自动补跑。

### 8.9 pipeline.py

- 串联全流程
- 收敛错误处理与统计

验收：返回结构化执行结果（条目数、失败数、耗时）。

---

## 9. 配置规范（必须）

`config.yaml` 至少包含：
- `schedule.timezone`
- `schedule.slots`（AM 08:00、PM 17:00）
- `schedule.compensate_on_startup`
- `sources[]`
- `filters`
- `summarizer`（可默认关闭）
- `push.enabled=false`
- `output.dir`

---

## 10. 日志与可观测性

每次任务至少记录：
- 任务标识：`date`, `slot`, `job_id`
- 抓取统计：总数、成功数、失败数
- 过滤统计：各规则过滤数量
- 摘要统计：调用数、失败数、降级数
- 输出结果：文件路径、耗时

日志级别建议：
- `INFO`：流程节点
- `WARNING`：单源失败、摘要降级
- `ERROR`：任务整体失败

---

## 11. 测试计划

### 11.1 单元测试

- URL 规范化
- 过滤规则
- 评分函数
- Markdown 渲染模板

### 11.2 集成测试

- 使用固定测试 RSS 输入跑完整 pipeline
- 校验生成 AM/PM 文件存在且结构正确

### 11.3 调度测试

- 人工构造“错过 AM”状态
- 启动后验证补偿执行与幂等

---

## 12. 风险与对策

1. RSSHub 路由不可用
- 对策：重试 + 超时 + 源级降级；必要时自建 RSSHub

2. 数据重复严重
- 对策：canonical_url + 指纹双重去重 + DB 唯一约束

3. LLM 不稳定或限流
- 对策：Top N 限制 + 失败降级 + 失败计数

4. 本地电脑关机错过任务
- 对策：补偿执行 + 状态持久化 + 幂等控制

---

## 13. 开发执行顺序（建议）

1. 建 DB 模型与配置加载
2. 完成抓取 + 硬过滤 + Markdown 生成（先不接 LLM）
3. 接入 scheduler 与补偿执行
4. 增加 scorer
5. 接入 summarizer 与降级
6. 最后补测试与日志完善

---

## 14. 完成定义（Definition of Done）

满足以下条件才算完成当前阶段：
- 能在 08:00/17:00 生成双 Markdown 文件
- 开机后可补偿执行未完成 slot
- 任意单源失败不会导致全流程失败
- 报告结构稳定、可读、可追溯
- 关键统计与错误日志可用于排查
