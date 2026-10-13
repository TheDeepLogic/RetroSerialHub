"""RSS news headlines and article viewing for Retro Serial OS."""

from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET

# In-memory cache of the most recently fetched news items
_LAST_NEWS_CACHE: list[dict] = []
_LAST_SOURCE: str = "npr"


def _clean_ascii(text: str) -> str:
    """Convert common Unicode punctuation to ASCII equivalents and drop non-ASCII."""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "--",
        "\u2026": "...",
        "\u00b0": " deg",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return "".join(ch for ch in text if ord(ch) < 128)


def _clean_html_to_ascii(text: str) -> str:
    """Unescape HTML entities, strip tags, and convert to clean ASCII."""
    if not text:
        return ""
    unescaped = html.unescape(text)
    stripped = re.sub(r"<[^>]+>", " ", unescaped)
    cleaned = re.sub(r"[ \t]+", " ", stripped)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return _clean_ascii("\n".join(lines))


def fetch_news_items(source: str = "npr", count: int = 5) -> list[dict]:
    """Fetch structured news items from clean RSS feeds and update cache."""
    global _LAST_NEWS_CACHE, _LAST_SOURCE
    source_lower = source.strip().lower()
    feed_urls = {
        "npr": "https://feeds.npr.org/1001/rss.xml",
        "tech": "https://news.ycombinator.com/rss",
        "hn": "https://news.ycombinator.com/rss",
        "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
    }
    feed_url = feed_urls.get(source_lower, feed_urls["npr"])
    source_name = (
        "NPR Top News"
        if "npr" in feed_url
        else ("Hacker News" if "ycombinator" in feed_url else "BBC World")
    )

    req = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    items_out = []
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read()
            tree = ET.fromstring(xml_data)
            raw_items = tree.findall(".//item")[:count]
            for idx, item in enumerate(raw_items, 1):
                title_elem = item.find("title")
                title = title_elem.text if title_elem is not None and title_elem.text else "No title"

                link_elem = item.find("link")
                link = link_elem.text if link_elem is not None and link_elem.text else ""

                desc_elem = item.find("description")
                desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""

                pub_elem = item.find("pubDate")
                pub = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                items_out.append(
                    {
                        "index": idx,
                        "source": source_name,
                        "title": _clean_ascii(title).strip(),
                        "link": link.strip(),
                        "summary": _clean_html_to_ascii(desc).strip(),
                        "published": _clean_ascii(pub).strip(),
                    }
                )
        if items_out:
            _LAST_NEWS_CACHE = list(items_out)
            _LAST_SOURCE = source_lower
    except Exception:
        pass
    return items_out


def get_cached_news_items() -> list[dict]:
    """Return the currently cached news items."""
    return list(_LAST_NEWS_CACHE)


def format_article(item: dict, width: int = 70) -> str:
    """Format an individual article for terminal display."""
    rule = "=" * width
    subrule = "-" * width
    lines = [
        rule,
        f"Article [{item.get('index', 1)}]: {item.get('title', 'No title')}",
        f"Source:    {item.get('source', 'News')}",
    ]
    if item.get("published"):
        lines.append(f"Published: {item.get('published')}")
    if item.get("link"):
        lines.append(f"URL:       {item.get('link')}")
    lines.append(subrule)
    summary = item.get("summary", "").strip()
    if summary and summary.lower() != "comments":
        lines.append(summary)
    else:
        lines.append("(No story summary in RSS feed. Use Full Webpage option to view article text.)")
    lines.append(rule)
    return "\n".join(lines)


def get_article_by_index(index: int, source: str | None = None) -> str:
    """Retrieve and format an article by its 1-based index from cache or fresh fetch."""
    global _LAST_NEWS_CACHE
    if not _LAST_NEWS_CACHE or (source and source != _LAST_SOURCE):
        fetch_news_items(source or "npr", count=max(6, index))

    for item in _LAST_NEWS_CACHE:
        if item.get("index") == index:
            return format_article(item)

    if _LAST_NEWS_CACHE:
        return f"Article [{index}] not found. Available articles: 1-{len(_LAST_NEWS_CACHE)}."
    return f"Article [{index}] not found and news feed could not be retrieved."


def get_full_article_by_index(index: int, source: str | None = None) -> str:
    """Fetch the full webpage text for an article by its 1-based index."""
    global _LAST_NEWS_CACHE
    if not _LAST_NEWS_CACHE or (source and source != _LAST_SOURCE):
        fetch_news_items(source or "npr", count=max(6, index))

    matched_item = None
    for item in _LAST_NEWS_CACHE:
        if item.get("index") == index:
            matched_item = item
            break

    if not matched_item:
        if _LAST_NEWS_CACHE:
            return f"Article [{index}] not found. Available articles: 1-{len(_LAST_NEWS_CACHE)}."
        return f"Article [{index}] not found."

    link = matched_item.get("link")
    if not link:
        return f"Article [{index}] has no URL link available.\n\n" + format_article(matched_item)

    try:
        from .viewer import extract_text_from_url

        web_text = extract_text_from_url(link)
        header = [
            "=" * 70,
            f"Full Web Article [{index}]: {matched_item.get('title', 'No title')}",
            f"Source: {matched_item.get('source', 'News')} | URL: {link}",
            "=" * 70,
            "",
        ]
        return "\n".join(header) + web_text
    except Exception as exc:
        return (
            f"Could not fetch full article webpage ({exc}). Showing summary:\n\n"
            + format_article(matched_item)
        )


def get_news(source: str = "npr", count: int = 5) -> str:
    """Fetch top headlines from clean RSS feeds."""
    source_lower = source.strip().lower()
    items = fetch_news_items(source_lower, count=count)
    if not items:
        source_name = (
            "NPR Top News"
            if "npr" in source_lower
            else ("Hacker News" if "hn" in source_lower or "tech" in source_lower else "BBC World")
        )
        return f"No news articles found from {source_name}."

    lines = [f"--- {items[0]['source']} Headlines ---"]
    for item in items:
        lines.append(f"[{item['index']}] {item['title']}")
    return "\n".join(lines)

