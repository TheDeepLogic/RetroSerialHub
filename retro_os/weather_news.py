"""Weather, news, and ambient daily briefing for retro terminals."""

from __future__ import annotations

import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


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


def get_weather(location: str | None = None) -> str:
    """Fetch live ASCII weather summary from wttr.in."""
    loc = location.strip() if location else ""
    if loc:
        encoded = urllib.parse.quote(loc)
        url = f"https://wttr.in/{encoded}?format=%l:+%C+%t+(Humidity:+%h,+Wind:+%w)"
    else:
        url = "https://wttr.in/?format=%l:+%C+%t+(Humidity:+%h,+Wind:+%w)"

    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            cleaned = _clean_ascii(data).strip()
            # If wttr.in returned an HTML error page or empty
            if not cleaned or "<html" in cleaned.lower():
                return f"Weather unavailable for '{loc or 'current location'}'."
            return cleaned
    except Exception as exc:
        return f"Weather lookup failed: {exc}"


def get_news(source: str = "npr", count: int = 5) -> str:
    """Fetch top headlines from clean RSS feeds."""
    source_lower = source.strip().lower()
    feed_urls = {
        "npr": "https://feeds.npr.org/1001/rss.xml",
        "tech": "https://news.ycombinator.com/rss",
        "hn": "https://news.ycombinator.com/rss",
        "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
    }
    feed_url = feed_urls.get(source_lower, feed_urls["npr"])
    source_name = "NPR Top News" if "npr" in feed_url else ("Hacker News" if "ycombinator" in feed_url else "BBC World")

    req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read()
            tree = ET.fromstring(xml_data)
            items = tree.findall(".//item")[:count]
            if not items:
                return f"No news articles found from {source_name}."

            lines = [f"--- {source_name} Headlines ---"]
            for idx, item in enumerate(items, 1):
                title_elem = item.find("title")
                title = title_elem.text if title_elem is not None and title_elem.text else "No title"
                lines.append(f"[{idx}] {_clean_ascii(title).strip()}")
            return "\n".join(lines)
    except Exception as exc:
        return f"News retrieval failed: {exc}"


def get_briefing(location: str | None = None, columns: int = 80) -> str:
    """Combine system date/time, weather, and top headlines for a retro desk briefing."""
    now_str = datetime.datetime.now().strftime("%A, %B %d, %Y  %I:%M %p")
    weather_summary = get_weather(location)
    news_summary = get_news("npr", count=4)

    lines = []
    if columns == 40:
        lines.append("=== RETRO DAILY BRIEFING ===")
        lines.append(now_str[:38])
        lines.append("----------------------------")
        lines.append("WEATHER:")
        lines.append(weather_summary[:38])
        lines.append("----------------------------")
        lines.append(news_summary)
        lines.append("============================")
    else:
        lines.append("====================== RETRO SERIAL HUB DAILY BRIEFING ======================")
        lines.append(now_str)
        lines.append("-" * 75)
        lines.append(f"CURRENT WEATHER : {weather_summary}")
        lines.append("-" * 75)
        lines.append(news_summary)
        lines.append("=" * 75)
    return "\n".join(lines)
