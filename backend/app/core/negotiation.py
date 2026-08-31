"""
JobCopilot - Salary Negotiation & Startup ESOP Equity Modeler
Benchmarks job offers against market percentiles, simulates startup equity
growth multiples, and generates professional counter-offer scripts.
"""

import re
from typing import List, Dict, Any, Optional
from app.core.cover_letter import CoverLetterGenerator


class SalaryNegotiationEngine:
    """Evaluates compensation packages and crafts tailored negotiation counter-offers."""

    # Market compensation benchmarks (base LPA / USD)
    MARKET_BENCHMARKS = {
        "Senior Software Engineer": {"p25": 22.0, "p50": 32.0, "p75": 45.0, "p90": 60.0},
        "Software Engineer": {"p25": 12.0, "p50": 18.0, "p75": 25.0, "p90": 35.0},
        "Staff Software Engineer": {"p25": 40.0, "p50": 55.0, "p75": 75.0, "p90": 100.0},
        "AI / ML Engineer": {"p25": 20.0, "p50": 30.0, "p75": 48.0, "p90": 70.0},
        "Engineering Manager": {"p25": 35.0, "p50": 50.0, "p75": 70.0, "p90": 95.0}
    }

    @classmethod
    def evaluate_offer(
        cls,
        base_salary_lpa: float,
        bonus_lpa: float = 0.0,
        equity_annual_lpa: float = 0.0,
        role_title: str = "Senior Software Engineer"
    ) -> Dict[str, Any]:
        """Calculates total compensation and benchmarks against market percentiles."""
        total_comp = round(base_salary_lpa + bonus_lpa + equity_annual_lpa, 2)

        # Match benchmark
        matched_bench = cls.MARKET_BENCHMARKS.get(role_title)
        if not matched_bench:
            for k in cls.MARKET_BENCHMARKS:
                if any(w.lower() in role_title.lower() for w in k.split()):
                    matched_bench = cls.MARKET_BENCHMARKS[k]
                    break
        if not matched_bench:
            matched_bench = cls.MARKET_BENCHMARKS["Senior Software Engineer"]

        # Determine percentile band
        if total_comp >= matched_bench["p90"]:
            percentile = "90th+ (Top of Market)"
            rating = "Exceptional"
            negotiation_room = "Focus negotiation on sign-on bonus or equity vesting acceleration."
        elif total_comp >= matched_bench["p75"]:
            percentile = "75th - 90th (Strong)"
            rating = "Competitive"
            negotiation_room = "Good leverage to negotiate a 10-15% increase or additional equity."
        elif total_comp >= matched_bench["p50"]:
            percentile = "50th - 75th (Median)"
            rating = "Fair Market"
            negotiation_room = "Solid room for negotiation; counter with 75th percentile benchmark."
        else:
            percentile = "< 50th (Below Market)"
            rating = "Below Market"
            negotiation_room = "Strongly recommend countering with standard market median numbers."

        return {
            "total_annual_comp_lpa": total_comp,
            "base_salary_lpa": base_salary_lpa,
            "bonus_lpa": bonus_lpa,
            "equity_annual_lpa": equity_annual_lpa,
            "market_percentile_band": percentile,
            "rating": rating,
            "benchmark_p50": matched_bench["p50"],
            "benchmark_p75": matched_bench["p75"],
            "negotiation_guidance": negotiation_room
        }

    @classmethod
    def model_startup_equity(
        cls,
        options_count: int,
        total_company_shares: int,
        current_valuation_usd: float,
        strike_price_per_share: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates ESOP ownership percentage and projected returns at growth exit multiples."""
        ownership_pct = (options_count / max(total_company_shares, 1)) * 100
        current_share_price = current_valuation_usd / max(total_company_shares, 1)
        current_equity_val = round(options_count * (current_share_price - strike_price_per_share), 2)

        multiples = [2.0, 3.0, 5.0, 10.0]
        scenarios = []
        for m in multiples:
            exit_val = current_valuation_usd * m
            exit_share_price = exit_val / max(total_company_shares, 1)
            payout = round(options_count * (exit_share_price - strike_price_per_share), 2)
            scenarios.append({
                "growth_multiple": f"{int(m)}x",
                "exit_valuation_usd": exit_val,
                "projected_payout_usd": payout
            })

        return {
            "options_granted": options_count,
            "ownership_percentage": round(ownership_pct, 4),
            "current_estimated_value_usd": max(current_equity_val, 0.0),
            "exit_scenarios": scenarios
        }

    @classmethod
    def generate_counter_offer_script(
        cls,
        candidate_name: str,
        company_name: str,
        role_title: str,
        offered_tc: str,
        desired_tc: str,
        leverage_points: Optional[List[str]] = None
    ) -> str:
        """Generates a professional, assertive, and respectful counter-offer email."""
        first_name = candidate_name.split()[0] if candidate_name else "Candidate"
        points = leverage_points or [
            "track record of scaling backend services with high reliability",
            "experience aligning directly with your roadmap goals"
        ]
        points_str = " and ".join(points)

        s1 = f"Thank you very much for the offer to join {company_name} as a {role_title}."
        s2 = f"I am genuinely excited about the team's mission and confident that my {points_str} will allow me to make an immediate impact."
        s3 = f"Given my background and current market benchmarks for this role, I would be thrilled to accept right away if we can adjust the total compensation from {offered_tc} to {desired_tc}."
        s4 = "I look forward to discussing how we can make this work."

        raw_script = f"Hi Team,\n\n{s1} {s2}\n\n{s3}\n\n{s4}\n\nBest regards,\n{candidate_name}"
        return CoverLetterGenerator.sanitize_anti_ai(raw_script)

    @classmethod
    def compare_multiple_offers(cls, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compares multiple job offers and generates side-by-side 4-year TC growth curves,
        liquid vs equity breakdown, and strategic negotiation leverage.
        """
        if not offers:
            return {"status": "empty", "offers_comparison": [], "recommendation": "No offers provided."}

        processed = []
        highest_y1 = 0
        highest_4yr = 0
        top_y1_company = ""
        top_4yr_company = ""

        for idx, o in enumerate(offers):
            comp = o.get("company", f"Offer {idx + 1}")
            base = float(o.get("base_lpa", 0.0))
            bonus = float(o.get("bonus_lpa", 0.0))
            equity_grant = float(o.get("equity_grant_total_lpa", 0.0))
            sign_on = float(o.get("sign_on_lpa", 0.0))
            vest_years = max(int(o.get("vesting_years", 4)), 1)
            equity_annual = round(equity_grant / vest_years, 2)
            eq_type = o.get("equity_type", "RSU (Public / Liquid)")

            # Year-by-year progression
            y1 = round(base + bonus + equity_annual + sign_on, 2)
            y2 = round(base + bonus + equity_annual, 2)
            y3 = round(base + bonus + equity_annual, 2)
            y4 = round(base + bonus + equity_annual, 2)
            four_year_total = round(y1 + y2 + y3 + y4, 2)

            if y1 > highest_y1:
                highest_y1 = y1
                top_y1_company = comp
            if four_year_total > highest_4yr:
                highest_4yr = four_year_total
                top_4yr_company = comp

            processed.append({
                "company": comp,
                "role_title": o.get("role_title", "Software Engineer"),
                "base_lpa": base,
                "bonus_lpa": bonus,
                "sign_on_lpa": sign_on,
                "equity_grant_total_lpa": equity_grant,
                "equity_annual_lpa": equity_annual,
                "equity_type": eq_type,
                "year_1_tc": y1,
                "year_2_tc": y2,
                "year_3_tc": y3,
                "year_4_tc": y4,
                "four_year_cumulative_tc": four_year_total,
                "liquid_percentage_y1": round(((base + bonus + sign_on) / max(y1, 0.1)) * 100, 1)
            })

        recommendation = (
            f"{top_4yr_company} delivers the highest 4-Year Total Compensation ({highest_4yr} LPA/USD). "
            f"If maximizing immediate first-year cash flow is your priority, {top_y1_company} leads with {highest_y1} LPA/USD. "
            f"Use the higher offer as leverage to negotiate sign-on or equity acceleration from your preferred company."
        )

        return {
            "status": "success",
            "offers_comparison": processed,
            "top_year_1_company": top_y1_company,
            "top_4_year_company": top_4yr_company,
            "highest_year_1_tc": highest_y1,
            "highest_4_year_tc": highest_4yr,
            "strategic_recommendation": recommendation
        }

    @classmethod
    def generate_advanced_counter_script(
        cls,
        candidate_name: str,
        target_company: str,
        role_title: str,
        current_base: str,
        current_equity: str,
        target_base: str,
        target_equity: str,
        competing_company: Optional[str] = None,
        competing_tc: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates tailored executive counter-offer email and phone negotiation talking points."""
        first_name = candidate_name.split()[0] if candidate_name else "there"

        competing_clause = ""
        if competing_company and competing_tc:
            competing_clause = (
                f" To be completely transparent, I am in the final stages with {competing_company} where the compensation package is around {competing_tc}."
                f" However, {target_company} remains my top choice because of the engineering team's mission and culture."
            )

        email_body = (
            f"Hi {target_company} Hiring Team,\n\n"
            f"Thank you so much for extending the offer to join as a {role_title}! I am thrilled about the opportunity to contribute to {target_company}'s core technical roadmap.\n\n"
            f"After reviewing the initial terms of {current_base} Base and {current_equity} Equity, and benchmarking against current market percentiles for this level,{competing_clause} "
            f"I would be ready to sign the agreement immediately if we can align on {target_base} Base Salary and {target_equity} Equity.\n\n"
            f"I am eager to make an immediate impact on the team and look forward to hearing your thoughts on whether we can bridge this gap.\n\n"
            f"Best regards,\n{candidate_name}"
        )

        clean_base = re.sub(r'[^\d.]', '', target_base.replace(',', ''))
        try:
            parsed_base = float(clean_base) if clean_base else 10.0
            if parsed_base >= 1000 and 'lpa' not in target_base.lower():
                parsed_base = parsed_base / 1000.0
        except ValueError:
            parsed_base = 10.0
        sign_on_k = max(1, int(parsed_base * 0.2))

        phone_talking_points = (
            f"1. Express strong enthusiasm: '{target_company} is my absolute #1 preference because of the team and architecture challenges.'\n"
            f"2. Anchor on value & benchmarks: 'Based on my track record and standard P85 market compensation for {role_title}, I am targeting {target_base} base.'\n"
            f"3. Offer immediate close: 'If you can meet me at {target_base} base + {target_equity} equity, I will cancel all other interview loops and sign today.'\n"
            f"4. If base is firm: 'If base is locked by band policy, can we bridge the gap with a ${sign_on_k}k sign-on bonus or additional stock grant?'"
        )

        return {
            "negotiation_email": CoverLetterGenerator.sanitize_anti_ai(email_body),
            "phone_talking_points": phone_talking_points
        }
