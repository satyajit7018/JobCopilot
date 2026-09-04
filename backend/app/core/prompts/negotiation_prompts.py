"""
JobCopilot - Salary Negotiation Prompts (v1.0)
Versioned templates for high-leverage compensation pushbacks and counter-offer emails.
"""

from typing import Dict, Any, Optional


class NegotiationPrompts:
    VERSION = "1.0.0"

    SYSTEM_PROMPT = (
        "You are an executive compensation coach specializing in Staff/Senior tech offers. "
        "Draft assertive, polished, and collaborative counter-offer emails that maximize Total Compensation "
        "without burning recruiter bridges or sounding adversarial. Focus on market comps and unique candidate leverage."
    )

    @classmethod
    def build_counter_script_prompt(
        cls,
        company_name: str,
        role_title: str,
        offered_base: float,
        target_base: float,
        offered_equity: float,
        target_equity: float,
        competing_offers_summary: Optional[str] = None
    ) -> str:
        leverage = f"Competing Offers / Market Leverage: {competing_offers_summary}\n" if competing_offers_summary else ""
        return (
            f"Company: {company_name}\n"
            f"Role: {role_title}\n"
            f"Current Offer: Base ₹{offered_base:.1f} LPA, Equity ₹{offered_equity:.1f} LPA\n"
            f"Target Counter: Base ₹{target_base:.1f} LPA, Equity ₹{target_equity:.1f} LPA\n"
            f"{leverage}\n"
            f"Instructions:\n"
            f"1. Express genuine enthusiasm for the team, engineering mission, and technical roadmap.\n"
            f"2. Clearly present the counter-offer proposal with rationales based on experience and market value.\n"
            f"3. Frame the request such that signing is immediate upon adjustment.\n"
            f"4. Provide two sections: 'Verbal Script (for phone calls)' and 'Written Email (for email/inbox)'."
        )
