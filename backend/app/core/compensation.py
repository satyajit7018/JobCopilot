"""
JobCopilot - Multi-Currency Compensation Engine
Handles conversions, parsing, and formatting across INR, USD, EUR, GBP, and CAD
for diverse ATS salary input fields (Annual, Monthly, Hourly, LPA).
"""

import re
from typing import Dict, Any, Tuple


class CompensationConverter:
    """Accurate multi-currency converter and ATS salary formatter."""

    # Fixed base exchange rates relative to INR (for stable, deterministic conversions)
    FX_RATES_TO_INR = {
        "INR": 1.0,
        "USD": 83.5,
        "EUR": 90.5,
        "GBP": 106.0,
        "CAD": 61.5,
        "AUD": 54.5,
        "SGD": 62.0
    }

    @classmethod
    def parse_to_base_inr(cls, ctc_string: str) -> float:
        """Parses strings like '15 LPA', '24 - 38 LPA', '₹15,00,000', '$120,000 - $160,000', '120k', '€85,000' into annual INR."""
        if not ctc_string:
            return 1500000.0  # Default 15 LPA

        text = str(ctc_string).lower().strip().replace(',', '')

        # Detect currency
        currency = "INR"
        if "$" in text or "usd" in text:
            currency = "USD"
        elif "€" in text or "eur" in text:
            currency = "EUR"
        elif "£" in text or "gbp" in text:
            currency = "GBP"
        elif "cad" in text or "c$" in text:
            currency = "CAD"
        elif "aud" in text or "a$" in text:
            currency = "AUD"
        elif "sgd" in text or "s$" in text:
            currency = "SGD"
        elif "₹" in text or "inr" in text or "lpa" in text or "lakh" in text:
            currency = "INR"

        # Extract numeric values (supports ranges like 28 - 35 or 120000 - 150000)
        num_matches = re.findall(r'[\d\.]+', text)
        if not num_matches:
            return 1500000.0

        nums = [float(n) for n in num_matches if n != '.']
        if not nums:
            return 1500000.0

        # If a range is present (e.g. 28 - 35), compute midpoint
        if len(nums) >= 2 and ("-" in text or "to" in text):
            val = (nums[0] + nums[1]) / 2.0
        else:
            val = nums[0]

        # Handle Indian LPA
        if currency == "INR":
            if "lpa" in text or "lakh" in text or "lac" in text or val < 100.0:
                return max(0.0, val * 100000.0)
            return max(0.0, val)

        # Handle 'k' multiplier (e.g. 120k)
        if "k" in text and val < 1000.0:
            val = val * 1000.0

        # Convert foreign currency to INR
        rate = cls.FX_RATES_TO_INR.get(currency, 83.5)
        return max(0.0, val * rate)

    @classmethod
    def parse_ctc(cls, ctc_string: str) -> float:
        """Legacy helper matching parse_to_base_inr."""
        return cls.parse_to_base_inr(ctc_string)

    @classmethod
    def format_for_ats(cls, base_inr: float, target_currency: str = "INR", unit: str = "ANNUAL") -> str:
        """Formats base INR into target ATS currency and unit strings."""
        target_currency = target_currency.upper()
        unit = unit.upper()
        rate = cls.FX_RATES_TO_INR.get(target_currency, 1.0)
        target_annual = base_inr / rate

        # INR Formats
        if target_currency == "INR":
            if unit in ["LPA", "LAKH"]:
                return f"{base_inr / 100000.0:.1f} LPA"
            if unit == "MONTHLY":
                return f"₹{int(base_inr / 12.0):,}"
            if unit == "HOURLY":
                return f"₹{int(base_inr / 2080.0):,}/hr"
            return f"₹{int(base_inr):,}"

        # USD Formats
        if target_currency == "USD":
            if unit == "HOURLY":
                return f"${target_annual / 2080.0:.2f}/hr"
            if unit == "MONTHLY":
                return f"${int(target_annual / 12.0):,}"
            return f"${int(target_annual):,}"

        # EUR Formats
        if target_currency == "EUR":
            if unit == "HOURLY":
                return f"€{target_annual / 2080.0:.2f}/hr"
            if unit == "MONTHLY":
                return f"€{int(target_annual / 12.0):,}"
            return f"€{int(target_annual):,}"

        # GBP Formats
        if target_currency == "GBP":
            if unit == "HOURLY":
                return f"£{target_annual / 2080.0:.2f}/hr"
            if unit == "MONTHLY":
                return f"£{int(target_annual / 12.0):,}"
            return f"£{int(target_annual):,}"

        return f"{int(target_annual):,} {target_currency}"

    @classmethod
    def get_salary_slider_equivalents(cls, expected_ctc: str) -> Dict[str, str]:
        """Calculates multi-currency real-time equivalents for UI sliders."""
        base_inr = cls.parse_to_base_inr(expected_ctc)
        return {
            "inr_lpa": cls.format_for_ats(base_inr, "INR", "LPA"),
            "inr_monthly": cls.format_for_ats(base_inr, "INR", "MONTHLY"),
            "usd_annual": cls.format_for_ats(base_inr, "USD", "ANNUAL"),
            "usd_hourly": cls.format_for_ats(base_inr, "USD", "HOURLY"),
            "eur_annual": cls.format_for_ats(base_inr, "EUR", "ANNUAL"),
            "gbp_annual": cls.format_for_ats(base_inr, "GBP", "ANNUAL")
        }
