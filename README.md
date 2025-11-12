# TrendRadar

Lightweight bootstrap of a news/trend aggregator. This initialization provides:

- Python virtual environment and basic dependencies
- Minimal configuration under `config/`
- A simple RSS aggregator in `main.py` that reads an OPML file and outputs an HTML report under `output/`
- Optional GitHub Actions workflow to run hourly

## Quick start

1. Create venv and install deps
   - `python3 -m venv .venv`
   - `.venv/bin/pip install -r requirements.txt`
2. Configure sources in `config/config.yaml`
3. Run: `.venv/bin/python main.py`
4. Check `output/latest.html` for the generated report


## 在线预览（GitHub Pages）
- 本仓库启用了基于 Actions 的 Pages 发布，默认每小时生成并部署 `output/`。
- 访问地址（fork 仓库）：https://waterlfhonda.github.io/TrendRadar/
- 手动触发：在 Actions 中运行工作流 “Hot News Crawler”。

## 开启推送（可选）
- 将 `config/config.yaml` 中的 `push.enable` 设为 `true`（默认关闭）。
- 在仓库 Settings → Secrets and variables → Actions 设置以下 Secrets（按需）：
  - `FEISHU_WEBHOOK_URL`（飞书）
  - `WEWORK_WEBHOOK_URL`（企业微信）
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`（Telegram）
  - `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_TO`（邮件）
  - `NTFY_TOPIC`, `NTFY_SERVER_URL`（ntfy）
  - `OPENAI_API_KEY`（若启用 AI 摘要）

