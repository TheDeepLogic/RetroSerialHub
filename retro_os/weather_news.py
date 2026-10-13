"""Weather, news, and ambient daily briefing for retro terminals."""

from __future__ import annotations

import datetime
import urllib.parse
import urllib.request

from .news import _clean_ascii, get_news


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
