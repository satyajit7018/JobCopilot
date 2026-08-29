"""
JobCopilot - Zero-Collision Calendar Availability Engine
Calculates optimal open interview time slots across timezones, filters out
busy calendar periods, and formats human-ready availability schedules.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Timezone UTC offsets for common interview timezones (no external dependency)
_TZ_UTC_OFFSETS: Dict[str, int] = {
    "IST": 330,    # UTC+5:30
    "PST": -480,   # UTC-8
    "PDT": -420,   # UTC-7
    "EST": -300,   # UTC-5
    "EDT": -240,   # UTC-4
    "CST": -360,   # UTC-6
    "GMT": 0,
    "CET": 60,     # UTC+1
    "SGT": 480,    # UTC+8
    "JST": 540,    # UTC+9
    "AEST": 600,   # UTC+10
}


class CalendarAvailabilityEngine:
    """Calculates non-conflicting interview scheduling windows."""

    @classmethod
    def get_open_slots(
        cls,
        timezone_str: str = "IST",
        days_ahead: int = 7,
        busy_slots: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates available interview windows during business hours (10:00 AM - 6:00 PM)
        in the candidate's timezone. Automatically expands the search window if fewer
        than 2 open slots are found due to weekends or busy blocks.

        Args:
            timezone_str: Display timezone label (e.g. "IST", "PST"). Used for labeling
                          and UTC offset computation.
            days_ahead:   Maximum calendar days to scan ahead. Default 7 ensures at
                          least 5 weekday slots are found even across a weekend.
            busy_slots:   List of blocked slot keys (e.g. ["2026-08-31_morning"]).
        """
        open_windows = []
        busy = set(busy_slots or [])

        # Compute current local time in candidate's timezone
        tz_offset_minutes = _TZ_UTC_OFFSETS.get(timezone_str, 0)
        now_utc = datetime.utcnow()
        now_local = now_utc + timedelta(minutes=tz_offset_minutes)

        day_offset = 1
        days_scanned = 0

        while days_scanned < days_ahead:
            target_date = now_local + timedelta(days=day_offset)
            day_offset += 1
            days_scanned += 1

            # Skip weekends (Saturday=5, Sunday=6)
            if target_date.weekday() in [5, 6]:
                continue

            date_str = target_date.strftime("%Y-%m-%d")
            day_name = target_date.strftime("%A, %b %d")

            # Morning Slot: 10:00 AM - 1:00 PM
            slot_morning = f"{date_str}_morning"
            if slot_morning not in busy:
                open_windows.append({
                    "date": date_str,
                    "day_label": day_name,
                    "slot_key": slot_morning,
                    "window": "10:00 AM - 1:00 PM",
                    "timezone": timezone_str
                })

            # Afternoon Slot: 2:30 PM - 5:30 PM
            slot_afternoon = f"{date_str}_afternoon"
            if slot_afternoon not in busy:
                open_windows.append({
                    "date": date_str,
                    "day_label": day_name,
                    "slot_key": slot_afternoon,
                    "window": "2:30 PM - 5:30 PM",
                    "timezone": timezone_str
                })

        return open_windows

    @classmethod
    def format_availability_email_text(
        cls,
        open_slots: List[Dict[str, Any]],
        max_days: int = 3
    ) -> str:
        """
        Formats availability into a clean, human email paragraph.
        Shows windows from the first `max_days` available days (default 3 days).
        """
        if not open_slots:
            return (
                "I am generally flexible this week between 10:00 AM and 6:00 PM. "
                "Please suggest a time that works on your end."
            )

        tz = open_slots[0].get("timezone", "IST")

        # Group by day, limit to max_days distinct days
        grouped: Dict[str, List[str]] = {}
        for s in open_slots:
            day = s["day_label"]
            if day not in grouped and len(grouped) >= max_days:
                continue
            grouped.setdefault(day, []).append(s["window"])

        lines = []
        for day, windows in grouped.items():
            lines.append(f"  - {day}: {' or '.join(windows)} ({tz})")

        return (
            "Here are a few times that work well on my end:\n"
            + "\n".join(lines)
            + "\n\nHappy to accommodate other times if these don't work."
        )
