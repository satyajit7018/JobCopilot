"""
JobCopilot - Salary Negotiation & Equity Modeler Router
Handles market compensation benchmarking, ESOP equity modeling, multi-offer comparison,
and tailored counter-offer negotiation scripts.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.models import User
from app.api.auth import get_current_user

router = APIRouter(tags=["negotiation"])


class OfferEvalRequest(BaseModel):
    base_salary_lpa: float
    bonus_lpa: float = 0.0
    equity_annual_lpa: float = 0.0
    role_title: str = "Senior Software Engineer"


class EquityModelRequest(BaseModel):
    options_count: int
    total_company_shares: int
    current_valuation_usd: float
    strike_price: float = 0.0


class MultiOfferCompareRequest(BaseModel):
    offers: List[Dict[str, Any]]


class AdvancedCounterOfferRequest(BaseModel):
    candidate_name: Optional[str] = None
    target_company: str
    role_title: str
    current_base: str
    current_equity: str
    target_base: str
    target_equity: str
    competing_company: Optional[str] = None
    competing_tc: Optional[str] = None


class CounterOfferRequest(BaseModel):
    candidate_name: Optional[str] = None
    company_name: str
    role_title: str
    offered_tc: str
    desired_tc: str
    leverage_points: Optional[List[str]] = None


@router.post("/negotiation/evaluate")
async def evaluate_offer_compensation(
    payload: OfferEvalRequest,
    current_user: User = Depends(get_current_user)
):
    """Benchmarks job offer against market percentiles."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "evaluation": SalaryNegotiationEngine.evaluate_offer(
            base_salary_lpa=payload.base_salary_lpa,
            bonus_lpa=payload.bonus_lpa,
            equity_annual_lpa=payload.equity_annual_lpa,
            role_title=payload.role_title
        )
    }


@router.post("/negotiation/equity")
async def model_equity(
    payload: EquityModelRequest,
    current_user: User = Depends(get_current_user)
):
    """Models startup ESOP ownership and future exit returns."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "equity_model": SalaryNegotiationEngine.model_startup_equity(
            options_count=payload.options_count,
            total_company_shares=payload.total_company_shares,
            current_valuation_usd=payload.current_valuation_usd,
            strike_price_per_share=payload.strike_price
        )
    }


@router.post("/salary/compare-offers")
@router.post("/negotiation/compare-offers")
async def compare_offers_endpoint(
    payload: MultiOfferCompareRequest,
    current_user: User = Depends(get_current_user)
):
    """Compares multiple offers with 4-year TC progression and liquidation analysis."""
    from app.core.negotiation import SalaryNegotiationEngine
    return SalaryNegotiationEngine.compare_multiple_offers(payload.offers)


@router.post("/salary/counter-script")
@router.post("/negotiation/advanced-counter")
async def generate_advanced_counter_script_endpoint(
    payload: AdvancedCounterOfferRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates tailored executive negotiation email and phone talking points."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "scripts": SalaryNegotiationEngine.generate_advanced_counter_script(
            candidate_name=payload.candidate_name or current_user.full_name,
            target_company=payload.target_company,
            role_title=payload.role_title,
            current_base=payload.current_base,
            current_equity=payload.current_equity,
            target_base=payload.target_base,
            target_equity=payload.target_equity,
            competing_company=payload.competing_company,
            competing_tc=payload.competing_tc
        )
    }


@router.post("/negotiation/counter-offer")
async def generate_counter_offer(
    payload: CounterOfferRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates an Anti-AI counter-offer negotiation email."""
    from app.core.negotiation import SalaryNegotiationEngine
    script = SalaryNegotiationEngine.generate_counter_offer_script(
        candidate_name=payload.candidate_name or current_user.full_name,
        company_name=payload.company_name,
        role_title=payload.role_title,
        offered_tc=payload.offered_tc,
        desired_tc=payload.desired_tc,
        leverage_points=payload.leverage_points
    )
    return {"status": "success", "counter_offer_script": script}
