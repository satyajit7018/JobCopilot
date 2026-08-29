"""
JobCopilot - Multi-Currency Compensation Engine
Translates salary expectations into target ATS currency and unit formats.
"""

import re
from typing import Dict, Any


class CompensationConverter:
    @staticmethod
    def parse_ctc(ctc_string: str) -> float:
        """Parses strings like '15 LPA', '₹15,00,000', '$120,000', '120k' into annual base INR."""
        text = ctc_string.lower().strip()
        num_match = re.search(r'[\d\.]+', text)
        if not num_match:
            return 1500000.0  # Default 15 LPA
        val = float(num_match.group(0))

        if "lpa" in text or "lakh" in text or "lac" in text or (val < 100 and "$" not in text):
            return val * 100000.0
        if "k" in text:
            return val * 1000.0 * 83.0  # Convert USD to INR
        if "$" in text or "usd" in text:
            return val * 83.0
        return val

    @classmethod
    def format_for_ats(cls, base_inr: float, target_currency: str = "INR", unit: str = "ANNUAL") -> str:
        if target_currency.upper() == "INR":
            if unit.upper() == "LPA":
                return f"{base_inr / 100000.0:.1f} LPA"
            if unit.upper() == "MONTHLY":
                return f"₹{int(base_inr / 12.0):,}"
            return f"₹{int(base_inr):,}"

        if target_currency.upper() == "USD":
            usd_annual = base_inr / 83.0
            if unit.upper() == "HOURLY":
                return f"${usd_annual / 2080.0:.2f}/hr"
            if unit.upper() == "MONTHLY":
                return f"${int(usd_annual / 12.0):,}"
            return f"${int(usd_annual):,}"

        return f"{int(base_inr):,}"
