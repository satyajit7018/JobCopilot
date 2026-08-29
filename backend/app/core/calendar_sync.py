"""
JobCopilot - Zero-Collision Calendar Availability Engine
Calculates optimal open interview time slots across timezones, filters out
busy calendar periods, and formats human-ready availability schedules.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class CalendarAvailabilityEngine:
    """Calculates non-conflicting interview scheduling windows."""

    @classmethod
    def get_open_slots(
        cls,
        timezone_str: str = "IST",
        days_ahead: int = 4,
        busy_slots: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates available interview windows during business hours (10:00 AM - 6:00 PM).
        """
        open_windows = []
        now = datetime.now()
        busy = set(busy_slots or [])

        for i in range(1, days_ahead + 1):
            target_date = now + timedelta(days=i)
            # Skip weekends
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
                    "window": "10:00 AM - 1:00 PM",
                    "timezone": timezone_str
                })

            # Afternoon Slot: 2:30 PM - 5:30 PM
            slot_afternoon = f"{date_str}_afternoon"
            if slot_afternoon not in busy:
                open_windows.append({
                    "date": date_str,
                    "day_label": day_name,
                    "window": "2:30 PM - 5:30 PM",
                    "timezone": timezone_str
                })

        return open_windows

    @classmethod
    def format_availability_email_text(cls, open_slots: List[Dict[str, Any]]) -> str:
        """Formats availability into a clean, human email paragraph."""
        if not open_slots:
            return "I am generally flexible this week between 10:00 AM and 6:00 PM."

        # Group by day
        grouped: Dict[str, List[str]] = {}
        tz = open_slots[0].get("timezone", "IST")
        for s in open_slots[:4]:
            day = s["day_label"]
            grouped.setdefault(day, []).append(s["window"])

        lines = []
        for day, windows in grouped.items():
            lines.append(f"• {day}: {' or '.join(windows)} {tz}")

        return "Here are a few times that work well on my end:\n" + "\n".join(lines)
