import os
import sys
import time
import html
import math
import re
from collections import defaultdict
from datetime import datetime, timezone

import requests
import feedparser
import yaml
from dateutil import parser as dateparser


CONFIG_PATH = os.path.join("config", "config.yaml")
FREQ_WORDS_PATH = os.path.join("config", "frequency_words.txt")
OUTPUT_DIR = os.path.join("output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "latest.html")


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_frequency_words(path: str):
    positive = set()
    negative = set()
    if not os.path.exists(path):
        return positive, negative
    content = open(path, "r", encoding="utf-8").read()
    tokens = content.split()
    for tok in tokens:
        t = tok.strip()
        if not t:
            continue
        polarity = 0
        if t.startswith("!"):
            polarity = -1
            t = t[1:]
        elif t.startswith("+"):
            polarity = 1
            t = t[1:]
        else:
            polarity = 1
        if not t:
            continue
        if polarity > 0:
            positive.add(t)
        elif polarity < 0:
            negative.add(t)
    return positive, negative


def score_title(title: str, pos_words: set, neg_words: set) -> int:
    t = title.lower()
    score = 0
    for w in pos_words:
        if w.lower() in t:
            score += 1
    for w in neg_words:
        if w.lower() in t:
            score -= 1
    return score


_TOKEN_SPLIT_RE = re.compile(r"[\W_]+", re.UNICODE)


def normalize_title(title: str) -> str:
    if not title:
        return ""
    # lower + strip punctuation/extra spaces
    t = title.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def tokenize_title(title: str):
    t = normalize_title(title)
    toks = [tok for tok in _TOKEN_SPLIT_RE.split(t) if len(tok) > 1]
    return set(toks)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def deduplicate_entries(entries):
    kept = []
    merged = 0
    sigs = []
    for e in entries:
        sig = tokenize_title(e.get("title") or "")
        is_dup = False
        for ksig in sigs:
            if jaccard(sig, ksig) >= 0.85:
                is_dup = True
                merged += 1
                break
        if not is_dup:
            kept.append(e)
            sigs.append(sig)
    return kept, merged


def parse_opml_for_feeds(opml_text: str):
    # Very simple OPML outline parser to extract xmlUrl attributes
    import xml.etree.ElementTree as ET
    feeds = []
    try:
        root = ET.fromstring(opml_text)
        for outline in root.iter("outline"):
            xml_url = outline.attrib.get("xmlUrl")
            if xml_url:
                feeds.append(xml_url)
    except ET.ParseError:
        pass
    return feeds


def fetch_opml(url: str) -> str:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text


def gather_rss_entries(feed_urls, per_feed_limit=10, total_cap=200):
    entries = []
    for i, url in enumerate(feed_urls):
        try:
            fp = feedparser.parse(url)
            for e in fp.entries[:per_feed_limit]:
                title = e.get("title") or ""
                link = e.get("link") or ""
                published = e.get("published") or e.get("updated") or ""
                published_ts = None
                if published:
                    try:
                        published_ts = dateparser.parse(published)
                    except Exception:
                        published_ts = None
                entries.append(
                    {
                        "title": title,
                        "link": link,
                        "published": published,
                        "published_ts": published_ts,
                        "source": fp.feed.get("title", url),
                    }
                )
            if len(entries) >= total_cap:
                break
        except Exception as ex:
            print(f"[warn] RSS fetch failed for {url}: {ex}")
        # Be polite to servers
        time.sleep(0.1)
    return entries[:total_cap]


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_html(entries, out_path, top_n=50, merged_count=0, error_count=0, page_title="TrendRadar Report"):
    ensure_output_dir()
    now_dt = datetime.now(timezone.utc).astimezone()
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    head = (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(page_title)}</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:920px;margin:24px auto;padding:0 16px;line-height:1.5;}"
        "h1{font-size:22px;margin:0 0 6px;} h2{margin-top:24px;} .item{margin:8px 0;padding:8px;border-bottom:1px solid #eee;}"
        ".meta{color:#666;font-size:12px;} .pill{display:inline-block;background:#eef;padding:2px 8px;border-radius:999px;margin-right:6px;font-size:12px;color:#334;}"
        ".section{margin-top:18px;border-top:2px solid #f3f3f3;padding-top:6px;}"
        "</style></head><body>"
    )
    body = [
        f"<h1>{html.escape(page_title)}</h1>",
        f"<div class='meta'>生成时间: {html.escape(now)} | 条目数: {len(entries)} | 合并去重: {merged_count} | 错误: {error_count}</div>",
    ]

    # Top-N section
    body.append("<div class='section'><h2>Top N</h2>")
    for idx, e in enumerate(entries[: max(1, int(top_n))], 1):
        title = html.escape(e.get("title") or "(untitled)")
        link = html.escape(e.get("link") or "")
        published = e.get("published_ts")
        if isinstance(published, datetime):
            published_str = published.astimezone().strftime("%Y-%m-%d %H:%M")
        else:
            published_str = html.escape(e.get("published") or "")
        source = html.escape(e.get("source") or "")
        score = e.get("score", 0)
        body.append(
            f"<div class='item'><span class='pill'>#{idx}</span><a href='{link}' target='_blank' rel='noopener'>{title}</a>"
            f"<div class='meta'>Source: {source} | Published: {published_str} | Score: {score:.3f}</div></div>"
        )
    body.append("</div>")

    # Group by source
    groups = defaultdict(list)
    for e in entries:
        groups[e.get("source") or "(unknown)"].append(e)
    body.append("<div class='section'><h2>按来源分组</h2>")
    for gname in sorted(groups.keys()):
        body.append(f"<h3>{html.escape(gname)}</h3>")
        for e in groups[gname][:50]:
            title = html.escape(e.get("title") or "(untitled)")
            link = html.escape(e.get("link") or "")
            published = e.get("published_ts")
            published_str = published.astimezone().strftime("%Y-%m-%d %H:%M") if isinstance(published, datetime) else html.escape(e.get("published") or "")
            score = e.get("score", 0)
            body.append(
                f"<div class='item'><a href='{link}' target='_blank' rel='noopener'>{title}</a>"
                f"<div class='meta'>Published: {published_str} | Score: {score:.3f}</div></div>"
            )
    body.append("</div>")
    for idx, e in enumerate(entries, 1):
        title = html.escape(e.get("title") or "(untitled)")
        link = html.escape(e.get("link") or "")
        published = e.get("published_ts")
        if isinstance(published, datetime):
            published_str = published.astimezone().strftime("%Y-%m-%d %H:%M")
        else:
            published_str = html.escape(e.get("published") or "")
        source = html.escape(e.get("source") or "")
        score = e.get("score", 0)
        body.append(
            f"<div class='item'><div><strong>{idx}. <a href='{link}' target='_blank' rel='noopener'>{title}</a></strong></div>"
            f"<div class='meta'>Source: {source} | Published: {published_str} | Score: {score}</div></div>"
        )
    tail = "</body></html>"
    html_str = head + "\n".join(body) + tail
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    # also write date-based output
    date_name = now_dt.strftime("%Y-%m-%d") + ".html"
    date_path = os.path.join(OUTPUT_DIR, date_name)
    with open(date_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    # ensure index.html redirect to latest
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write("<meta http-equiv=\"refresh\" content=\"0;url=latest.html\">")


def run_rss_pipeline(source_cfg, pos_words, neg_words):
    url = source_cfg.get("url")
    if not url:
        print("[warn] RSS source missing url in config")
        return []
    print(f"[info] Fetching OPML: {url}")
    opml_text = fetch_opml(url)
    feed_urls = parse_opml_for_feeds(opml_text)
    if not feed_urls:
        print("[warn] No feeds discovered in OPML")
        return []
    print(f"[info] Discovered {len(feed_urls)} feeds; sampling first 25")
    feed_urls = feed_urls[:25]
    entries = gather_rss_entries(feed_urls)
    # compute keyword score first
    for e in entries:
        e["kw_score"] = score_title(e.get("title") or "", pos_words, neg_words)
    return entries


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"[error] Missing config file: {CONFIG_PATH}")
        sys.exit(1)

    cfg = load_yaml(CONFIG_PATH)
    pos_words, neg_words = load_frequency_words(FREQ_WORDS_PATH)
    platforms = cfg.get("platforms", [])
    # settings
    weights = cfg.get("weight", {}) if isinstance(cfg.get("weight"), dict) else {}
    half_life_min = weights.get("time_decay_half_life_minutes", 180)
    try:
        half_life_min = float(half_life_min) if half_life_min else 180.0
    except Exception:
        half_life_min = 180.0
    report = cfg.get("report", {}) if isinstance(cfg.get("report"), dict) else {}
    top_n = int(report.get("top_n", 50) or 50)
    page_title = (cfg.get("web", {}) or {}).get("page_title", "TrendRadar Report")

    all_entries = []
    error_count = 0
    for p in platforms:
        pid = p.get("id")
        ptype = p.get("type")
        print(f"[info] Processing platform: {pid}")
        if ptype == "rss":
            entries = run_rss_pipeline(p, pos_words, neg_words)
            all_entries.extend(entries)
        elif pid in {"baidu", "zhihu"}:
            print(f"[info] Skipping '{pid}' placeholder (not implemented in bootstrap)")
        else:
            print(f"[warn] Unknown platform type: {ptype}")

    # scoring with time decay
    now = datetime.now(timezone.utc)
    for e in all_entries:
        base = float(e.get("kw_score", 0))
        ts = e.get("published_ts")
        if isinstance(ts, datetime) and half_life_min > 0:
            dtm = max(0.0, (now - ts).total_seconds() / 60.0)
            decay = math.exp(-dtm / half_life_min)
        else:
            decay = 1.0
        e["score"] = base * decay

    # deduplicate similar titles
    all_entries.sort(key=lambda x: (
        x.get("score", 0),
        x.get("published_ts") or datetime.fromtimestamp(0, tz=timezone.utc),
    ), reverse=True)
    deduped, merged = deduplicate_entries(all_entries)

    if not deduped:
        print("[warn] No entries collected. Check your configuration and network.")
    else:
        print(f"[info] Collected {len(all_entries)} entries (after dedup {len(deduped)}, merged {merged}). Generating HTML...")
        generate_html(deduped, OUTPUT_FILE, top_n=top_n, merged_count=merged, error_count=error_count, page_title=page_title)
        print(f"[info] Wrote report to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
