import re
from datetime import date, timedelta


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _build_date(year, month, day):
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _parse_leave_date(message):
    text = message.lower()
    today = date.today()

    relative_dates = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
    }
    for word, value in relative_dates.items():
        if re.search(rf"\b{word}\b", text):
            return value

    iso_match = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if iso_match:
        parsed = _build_date(*iso_match.groups())
        if parsed:
            return parsed

    numeric_match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", text)
    if numeric_match:
        day, month, year = numeric_match.groups()
        parsed = _build_date(year, month, day)
        if parsed:
            return parsed

    month_names = "|".join(MONTHS.keys())
    month_first = re.search(
        rf"\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(\d{{4}})\b",
        text,
    )
    if month_first:
        month, day, year = month_first.groups()
        parsed = _build_date(year, MONTHS[month], day)
        if parsed:
            return parsed

    day_first = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?:,)?\s+(\d{{4}})\b",
        text,
    )
    if day_first:
        day, month, year = day_first.groups()
        parsed = _build_date(year, MONTHS[month], day)
        if parsed:
            return parsed

    return None


def process(user_request):
    leave_date = _parse_leave_date(user_request)
    today = date.today()

    if not leave_date:
        return {
            "agent": "Leave Apply Agent",
            "task": "Please provide a leave date, for example: apply leave for tomorrow or apply leave for 2026-06-05."
        }

    days_from_today = (leave_date - today).days
    formatted_date = leave_date.strftime("%d %b %Y")

    if days_from_today < -9:
        return {
            "agent": "Leave Apply Agent",
            "task": f"Leave cannot be applied for {formatted_date} because it is more than 9 days in the past."
        }

    if days_from_today < 0:
        return {
            "agent": "Leave Apply Agent",
            "task": f"Backdated leave request prepared for {formatted_date}. It is within the allowed 9-day range and can be submitted for approval."
        }

    return {
        "agent": "Leave Apply Agent",
        "task": f"Leave request prepared for {formatted_date}. It is eligible for submission."
    }
