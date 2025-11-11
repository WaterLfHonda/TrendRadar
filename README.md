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

