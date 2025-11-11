import os
import sys
import time
import html
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


def generate_html(entries, out_path):
    ensure_output_dir()
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    head = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>TrendRadar Report</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:880px;margin:24px auto;padding:0 16px;}"
        "h1{font-size:22px;} .item{margin:10px 0;padding:8px;border-bottom:1px solid #eee;}"
        ".meta{color:#666;font-size:12px;}</style></head><body>"
    )
    body = [f"<h1>TrendRadar Report</h1><div class='meta'>Generated at {html.escape(now)}</div>"]
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
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(body) + tail)


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
    for e in entries:
        e["score"] = score_title(e.get("title") or "", pos_words, neg_words)
    # Sort by score desc, then recency
    entries.sort(
        key=lambda x: (
            x.get("score", 0),
            x.get("published_ts") or datetime.fromtimestamp(0, tz=timezone.utc),
        ),
        reverse=True,
    )
    return entries


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"[error] Missing config file: {CONFIG_PATH}")
        sys.exit(1)

    cfg = load_yaml(CONFIG_PATH)
    pos_words, neg_words = load_frequency_words(FREQ_WORDS_PATH)
    platforms = cfg.get("platforms", [])

    all_entries = []
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

    if not all_entries:
        print("[warn] No entries collected. Check your configuration and network.")
    else:
        print(f"[info] Collected {len(all_entries)} entries. Generating HTML...")
        generate_html(all_entries, OUTPUT_FILE)
        print(f"[info] Wrote report to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

