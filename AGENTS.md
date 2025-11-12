# AGENTS — TrendRadar 多智能体设计（Agents Design）

> TL;DR：TrendRadar 以 Ingest → Dedup/Cluster → Rank → Summarize → Publish → Notify 的流水线自动聚合热点并生成 `output/latest.html`，由 GitHub Actions 每小时触发；BestBlogs 作为高质量 RSS 上游。

```mermaid
flowchart TD
  A[Ingestor\n抓取] --> B[Deduplicator & Clusterer\n去重/聚类]
  B --> C[Ranker\n加权排序]
  C --> D[Summarizer\n摘要生成]
  D --> E[Publisher\n日报生成]
  E --> F[Notifier\n多渠道推送]
  G[[MCP Analyst\n对话式趋势分析(未来)]] -. 读取日报/历史 .-> G
  E -->|产出 HTML| H[(output/latest.html)]
```

## 1) 项目简介与核心目标
- 功能定位：新闻与趋势聚合系统，面向“减负阅读+快速洞察”。
- 设计目标：自动抓取多源热点、去重聚类、权重排序、（可选）摘要生成、发布与推送，形成可被 LLM/MCP 再利用的统一日报。
- 技术特性：Python、GitHub Actions 定时、Docker 可选部署、未来可结合 MCP（Model Context Protocol）。
- 与 BestBlogs 的关系：TrendRadar 通过 `config.yaml` 中的 `rss_bestblogs` 指向 BestBlogs 提供的 OPML（如 `BestBlogs_RSS_Articles.opml`），批量解析为 RSS 源进行抓取。

## 2) Agents 一览表
| 名称 | 职责 | 触发条件 | 输入 | 输出 | 依赖 |
|------|------|-----------|------|------|------|
| Ingestor | 抓取多源数据（RSS/占位的百度/知乎等） | Actions 定时任务 / 手动触发 | config.yaml、BestBlogs OPML | raw JSON（entries） | requests、feedparser |
| Deduplicator & Clusterer | 去重、主题聚类（规划） | Ingest 完成后 | raw JSON | clean JSON / clusters | 待定（SimHash/BM25/向量） |
| Ranker | 关键词权重与时间因子排序 | Dedup 完成后 | clean JSON + frequency_words | scored JSON | python-dateutil |
| Summarizer | AI 摘要生成（规划） | Rank 完成后 | scored JSON + prompts | brief JSON | OpenAI/Gemini/本地LLM |
| Publisher | 生成日报 HTML | Summarize 完成后 | brief/scored JSON | output/latest.html | — |
| Notifier | 多渠道推送（规划） | Publish 完成后 | latest.html | webhook/邮件/ntfy | 各渠道 API/SMTP |
| MCP Analyst | 对话式趋势分析（未来） | 用户交互触发 | 历史数据缓存/日报 | 分析报告 / 对话响应 | MCP Server + LLM |

注：当前代码已覆盖 Ingestor（RSS）、简化 Ranker 与 Publisher；其余为规划。

## 3) Prompt Templates（LLM 提示词模板）
所有模板均以中文输出；变量以 `{{var}}` 表示。

### 3.1 Title Normalization（标题规范化）
输入变量：`title`, `platform`, `source`
输出格式：
```
{
  "title_norm": "{{title_规范化后}}",
  "notes": "若含口语或噪音，给出处理说明"
}
```
约束：不改变事实；不添加无依据信息；不超过 80 字。

### 3.2 Summary Generation（摘要生成）
输入变量：`title`, `snippets`, `link`, `platform`, `rank`
输出格式：
```
{
  "summary": "30-60 字核心摘要",
  "key_points": ["<=20字要点1", "<=20字要点2", "<=20字要点3"]
}
```
约束：客观、中立、可核验；必要时附“待核实”。

### 3.3 Tag Extraction（标签建议）
输入变量：`title`, `summary`
输出格式：
```
{
  "tags": ["#AI", "#芯片", "#政策"]
}
```
约束：3–5 个；全局可检索；不使用冷僻缩写。

### 3.4 Notify Card（多渠道推送卡片）
输入变量：`title`, `summary`, `link`, `score`, `platform`
输出格式：
```
{
  "card_title": "【{{platform}}】{{title}}",
  "card_body": "{{summary}}",
  "card_link": "{{link}}"
}
```
约束：适配 IM；正文不超 120 字；包含可点击链接。

## 4) Data Contracts（数据契约）

说明：以下 JSON 为“阶段产出形态”。当前实现以内存结构为主；字段命名与 `main.py` 一致优先，其余为推荐/规划字段并注明。

### 4.1 raw JSON（Ingestor 输出，当前实现）
```json
{
  "title": "string",
  "link": "string",
  "published": "string",
  "published_ts": "ISO-8601 | null",
  "source": "string"
}
```

可选/推荐：`platform`（如 "rss"），`id`（url 哈希）。

### 4.2 clean JSON（Dedup/Cluster 输出，规划）
```json
{
  "entries": [ /* 去重后的 raw entries */ ],
  "clusters": [
    {"cluster_id": "string", "label": "string", "entries": [/* raw entries */]}
  ]
}
```

### 4.3 scored JSON（Ranker 输出，当前实现有 score）
```json
{
  "title": "string",
  "link": "string",
  "published": "string",
  "published_ts": "ISO-8601 | null",
  "source": "string",
  "score": 0
}
```

### 4.4 brief JSON（Summarizer 输出，规划）
```json
{
  "title": "string",
  "link": "string",
  "summary": "string",
  "tags": ["string"]
}
```

### 4.5 notify payload（Notifier 输入，规划）
```json
{
  "channel": "feishu|wework|email|ntfy",
  "card_title": "string",
  "card_body": "string",
  "card_link": "string"
}
```

### 4.6 发布产物（Publisher 输出，当前实现）
```
路径：output/latest.html
说明：静态 HTML，含条目、来源与时间，按 score 与时间倒序。
```

## 5) Config 与 Secrets 映射
- 配置文件：`config/config.yaml`
  - `run.mode`：运行模式（daily）
  - `run.cron`：Actions 定时表达式（"0 * * * *"）
  - `weight.rank_weight` / `weight.frequency_weight` / `weight.hotness_weight`：排序参数（当前实现以关键词分为主）
  - `platforms[]`：平台定义（包括 `rss_bestblogs`，指向 OPML URL）
- 关键词：`config/frequency_words.txt`（`+词` 计正，`!词` 计负）
- GitHub Secrets（规划/可选）：
  - `FEISHU_WEBHOOK_URL`、`WEWORK_WEBHOOK_URL`
  - `EMAIL_FROM` / `EMAIL_PASSWORD` / `EMAIL_TO`
  - `NTFY_TOPIC` / `NTFY_SERVER_URL`
  - `OPENAI_API_KEY`（若启用 AI 摘要）

注：不臆造不存在的配置；当前仓库未包含 `push.channels[]`，如需启用通知，请以 Secrets/ENV 注入并在代码中消费。

## 6) Metrics（监控指标）
- 抓取成功率（ingest_success_rate）
- 去重率（dedup_ratio）
- Top-10 命中率（top10_precision，基于人工标注或启发式）
- 推送送达率（notify_delivery_rate）
- 端到端延迟（pipeline_latency_min）

## 7) Milestones（里程碑）
| 阶段 | 内容 | 完成条件 |
|------|------|-----------|
| M1 | 跑通定时抓取与 HTML 生成 | Actions 运行成功 + output/latest.html 存在 |
| M2 | 完成摘要与推送通道联通 | 日报含摘要 + 成功推送 |
| M3 | 集成 MCP Analyst | 可自然语言查询“最近三天趋势” |

## 8) Design Notes（设计理念）
- 从最小可用闭环（MVP）开始，先打通 RSS→HTML；
- 保持轻量依赖与可移植性；
- 先 deterministic pipelines，后引入 LLM；
- TrendRadar 定位为“聚合与洞察”，避免凭空生成；
- 输出单一入口：统一产出 `output/latest.html` 供下游（包括 MCP）消费。

---

✅ 文件生成时间：2025-11-12 22:45:54 JST
