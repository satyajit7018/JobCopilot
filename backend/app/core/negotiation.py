"""
JobCopilot - Salary Negotiation & Startup ESOP Equity Modeler
Benchmarks job offers against market percentiles, simulates startup equity
growth multiples, and generates professional counter-offer scripts.
"""

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
