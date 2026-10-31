"""The clock the whole agent reads: Indian Standard Time, whatever the server's zone is.

The server may run in UTC (or anything else). "An hour ago" said at 00:30 IST on the 31st is
the 30th, so every "today" / "now" in the agent comes from here, never from date.today().
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# A fixed offset, not a zoneinfo key: the host may lack tzdata, and IST has no DST.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now() -> datetime:
    return datetime.now(IST)


def today() -> date:
    return now().date()


def spoken(d: date) -> str:
    """A date the TTS reads well: '30 October 2026'."""
    return f"{d.day} {d:%B %Y}"
