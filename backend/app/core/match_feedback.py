"""
"Not interested because...": turns a reason into a rule that new searches follow.

Each rule is small and readable so the user can see and remove it in Profile:
  seniority  "Staff" roles                    (only when the title says a level)
  location   jobs in "bangalore"              (on-site only; remote jobs still show)
  field      "frontend engineer" roles        (the job title without level words)
  salary     jobs paying up to 45 LPA         (only when the salary could be read)
  company    jobs at "acme"
"""

import hashlib
import re
from typing import Any, Dict, List, Optional

from app.core.match_scorer import MatchScorer

REASONS = ("seniority", "location", "field", "salary", "company", "other")

_LEVEL_WORDS = r"\b(intern|internship|junior|jr\.?|senior|sr\.?|staff|principal|lead|entry[- ]level|graduate|mid[- ]level|i{1,3}|iv|[1-4])\b"


def _rule(kind: str, value: Any, label: str) -> Dict[str, Any]:
    rule_id = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()[:10]
    return {"id": rule_id, "kind": kind, "value": value, "label": label}


def core_title(title: str) -> str:
    """'Senior Backend Engineer (Payments) - II' -> 'backend engineer'."""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", (title or "").lower())
    t = re.split(r"\s[-–|,]\s|,", t)[0]
    t = re.sub(_LEVEL_WORDS, " ", t)
    t = re.sub(r"[^a-z0-9+#/ ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _city(location: str) -> str:
    first = re.split(r"[,/|·]", (location or "").lower())[0]
    return re.sub(r"\s+", " ", first).strip()


def _is_remote(location: str) -> bool:
    return bool(re.search(r"\bremote\b", (location or "").lower()))


def salary_max_lpa(salary: Optional[str]) -> Optional[float]:
    """Top of an Indian 'LPA' range ('28 - 45 LPA' -> 45). Other currencies aren't compared."""
    if not salary or "lpa" not in salary.lower():
        return None
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", salary)]
    return max(numbers) if numbers else None


def rule_for(reason: str, job) -> Optional[Dict[str, Any]]:
    """The rule a reason creates for this job, or None when there's nothing reliable to learn."""
    if reason == "seniority":
        level = MatchScorer.infer_job_seniority(job.title, "")  # title only: the level must be explicit
        if level == "Mid-Level":
            return None
        return _rule("seniority", level, f"{level} roles")
    if reason == "location":
        if _is_remote(job.location):
            return None
        city = _city(job.location)
        return _rule("location", city, f"On-site jobs in {city.title()}") if city else None
    if reason == "field":
        core = core_title(job.title)
        return _rule("field", core, f"“{core.title()}” roles") if len(core) >= 3 else None
    if reason == "salary":
        top = salary_max_lpa(job.salary_range)
        return _rule("salary", top, f"Jobs paying up to {top:g} LPA") if top else None
    if reason == "company":
        name = (job.company or "").strip()
        return _rule("company", name.lower(), f"Jobs at {name}") if name else None
    return None


def no_rule_note(reason: str) -> str:
    """Why a reason didn't create a rule, in words the user sees."""
    return {
        "seniority": "Noted. The job title doesn't name a level, so there's nothing to skip by.",
        "location": "Noted. This job is open to remote work, so we won't skip jobs by its location.",
        "salary": "Noted. This job doesn't list pay in LPA, so there's nothing to compare against.",
        "field": "Noted. We couldn't tell the job's field from its title.",
    }.get(reason, "Thanks, noted.")


def skips(rules: List[Dict[str, Any]], title: str, location: str, company: str, salary: Optional[str]) -> bool:
    """True when a posting matches any of the user's rules."""
    for r in rules:
        kind, value = r.get("kind"), r.get("value")
        if kind == "seniority" and MatchScorer.infer_job_seniority(title, "") == value:
            return True
        if kind == "location" and not _is_remote(location) and value and value in (location or "").lower():
            return True
        if kind == "field" and value and core_title(title) == value:
            return True
        if kind == "salary":
            top = salary_max_lpa(salary)
            if top is not None and top <= float(value):
                return True
        if kind == "company" and value and value in (company or "").lower():
            return True
    return False
