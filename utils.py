import re
from datetime import datetime, timedelta
from typing import Optional

RELATIVE_KEYWORDS = {
    'idag': 'today',
    'igår': 'yesterday',
    'just nu': 'just now',
    'justnow': 'just now',
}

SWEDISH_MONTHS = {
    'jan': 1, 'januari': 1,
    'feb': 2, 'februari': 2,
    'mar': 3, 'mars': 3,
    'apr': 4, 'april': 4,
    'maj': 5,
    'jun': 6, 'juni': 6,
    'jul': 7, 'juli': 7,
    'aug': 8, 'augusti': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'okt': 10, 'oktober': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

ENGLISH_MONTHS = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

MONTH_MAP = {**SWEDISH_MONTHS, **ENGLISH_MONTHS}

RELATIVE_PATTERN = re.compile(r"(?P<value>\d+)\s*(?P<unit>day|days|hour|hours|week|weeks|\bd\b|\bh\b|\bw\b)", re.I)

ISO_PATTERN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
SLASH_PATTERN = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
MONTH_FIRST_PATTERN = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s*(\d{2,4})?\b")
DAY_FIRST_PATTERN = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s*(\d{2,4})?\b")


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Convert various date strings into ISO format (YYYY-MM-DD)."""
    if not date_str:
        return None

    text = date_str.strip().lower()
    if not text:
        return None

    now = datetime.now()

    # Relative keywords (today, yesterday, etc.)
    for key, replacement in RELATIVE_KEYWORDS.items():
        text = text.replace(key, replacement)

    if 'just now' in text or 'just nu' in text:
        return now.strftime('%Y-%m-%d')

    if 'today' in text:
        return now.strftime('%Y-%m-%d')

    if 'yesterday' in text:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')

    # Relative patterns like "2 days ago"
    match = re.search(r"(\d+)\s+(day|days)\s+ago", text)
    if match:
        days = int(match.group(1))
        return (now - timedelta(days=days)).strftime('%Y-%m-%d')

    match = re.search(r"(\d+)\s+(hour|hours)\s+ago", text)
    if match:
        hours = int(match.group(1))
        return (now - timedelta(hours=hours)).strftime('%Y-%m-%d')

    match = re.search(r"(\d+)\s+(week|weeks)\s+ago", text)
    if match:
        weeks = int(match.group(1))
        return (now - timedelta(weeks=weeks)).strftime('%Y-%m-%d')

    # Time-of-day only (e.g., "Igår 20:56" already handled; plain "20:56" -> today)
    if re.match(r"^\d{1,2}:\d{2}$", text):
        return now.strftime('%Y-%m-%d')

    # ISO format
    iso_match = ISO_PATTERN.search(text)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"

    # Slash or dash format 12/10/2025
    slash_match = SLASH_PATTERN.search(text)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = int(slash_match.group(3))
        if year < 100:
            year += 2000
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Month first e.g. Oct 26, 2025
    month_first = MONTH_FIRST_PATTERN.search(text)
    if month_first:
        month_str = month_first.group(1).lower()
        day = int(month_first.group(2))
        year = month_first.group(3)
        month = MONTH_MAP.get(month_str[:3])
        if month:
            year_val = int(year) if year else now.year
            if not year and datetime(year_val, month, day) > now:
                year_val -= 1
            return f"{year_val:04d}-{month:02d}-{day:02d}"

    # Day first e.g. 26 okt 2025
    day_first = DAY_FIRST_PATTERN.search(text)
    if day_first:
        day = int(day_first.group(1))
        month_str = day_first.group(2).lower()
        year = day_first.group(3)
        month = MONTH_MAP.get(month_str[:3])
        if month:
            year_val = int(year) if year else now.year
            if not year and datetime(year_val, month, day) > now:
                year_val -= 1
            return f"{year_val:04d}-{month:02d}-{day:02d}"

    # If nothing matches, return None
    return None
