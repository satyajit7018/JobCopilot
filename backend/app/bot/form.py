"""
JobCopilot - What goes into an application form, and what is still missing.

Every answer typed into an employer's form comes from here, so the rules live in one place:
only the user's own data, never a guess, never a leftover {placeholder}.
"""

import logging
from typing import Any, List, Optional

from app.core.models import CandidateProfile
from app.core.vector_vault import PLACEHOLDER, vault

logger = logging.getLogger(__name__)

def answer_for(
    question: str,
    profile: CandidateProfile,
    user_id: str = "",
    company: str = "",
    role: str = "",
    job_id: str = "",
) -> Optional[str]:
    """The user's answer to a form question, or None to leave it for them.

    Only the profile and answers the user gave to the same (or a confirmed) wording are typed.
    A similar question's answer is a suggestion for the user to check, never filled here.
    """
    match = vault.find_answer(
        question,
        profile=profile,
        user_id=user_id or profile.user_id,
        job_id=job_id or None,
        company=company,
        role=role,
    )
    if match.source not in ("profile", "saved") or not match.answer or PLACEHOLDER.search(match.answer):
        return None
    return match.answer


async def fill_field(page: Any, target: Any, value: Optional[str]) -> bool:
    """Puts a value into a field (a selector or an element). False if there's nothing to put or nowhere to put it."""
    if not value or not str(value).strip():
        return False
    element = await page.query_selector(target) if isinstance(target, str) else target
    if not element:
        return False
    await element.fill(str(value))
    return True


# Required fields still empty after filling, named the way the form shows them.
_MISSING_REQUIRED_JS = """
() => {
  const nameOf = (el) => {
    const label = el.labels && el.labels[0] ? el.labels[0].innerText : "";
    return (label || el.getAttribute("aria-label") || el.placeholder || el.name || el.id || "A required field")
      .replace(/\\s*\\*\\s*$/, "").trim();
  };
  const missing = [];
  const radioGroups = new Set();
  for (const el of document.querySelectorAll("input, textarea, select")) {
    const required = el.required || el.getAttribute("aria-required") === "true";
    if (!required || el.disabled || el.type === "hidden") continue;
    let empty;
    if (el.type === "radio") {
      if (radioGroups.has(el.name)) continue;
      radioGroups.add(el.name);
      empty = !document.querySelector(`input[type="radio"][name="${CSS.escape(el.name)}"]:checked`);
    } else if (el.type === "checkbox") {
      empty = !el.checked;
    } else if (el.type === "file") {
      empty = !(el.files && el.files.length);
    } else {
      empty = !String(el.value || "").trim();
    }
    if (empty) missing.push(nameOf(el));
  }
  return missing;
}
"""


async def missing_required(page: Any) -> List[str]:
    """Labels of required fields the form still needs. A form with any of these is never submitted."""
    try:
        return list(await page.evaluate(_MISSING_REQUIRED_JS))
    except Exception:
        logger.warning("form: could not check required fields", exc_info=True)
        # Unknown is not "complete": treat the check itself as a missing answer.
        return ["Required fields could not be checked"]
