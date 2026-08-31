"""
JobCopilot - Provider-Agnostic LLM Client & Deterministic Fallback Engine
Supports OpenAI, Anthropic Claude, and rule-based deterministic fallback.
Guarantees 100% offline availability and zero external dependency failures.
"""

import json
import logging
from typing import Optional, Dict, Any, List
import httpx

from app.core.settings import settings

logger = logging.getLogger("jobcopilot.llm")


class LLMClient:
    """Unified LLM inference client with automatic deterministic fallback."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 12.0
    ):
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.model = model or settings.DEFAULT_LLM_MODEL
        self.timeout = timeout

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        fallback_fn = None
    ) -> str:
        """
        Generates text completion via configured LLM provider.
        If provider is 'local', unconfigured, or fails, transparently executes fallback_fn.
        """
        # 1. OpenAI Provider
        if self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    res = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model or "gpt-4o-mini",
                            "messages": messages,
                            "temperature": 0.3
                        }
                    )
                    if res.status_code == 200:
                        data = res.json()
                        content = data["choices"][0]["message"]["content"]
                        logger.info(f"OpenAI completion generated ({len(content)} chars)")
                        return content.strip()
            except Exception as e:
                logger.warning(f"OpenAI call failed, using deterministic fallback: {e}")

        # 2. Anthropic Provider
        if self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    headers = {
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": self.model or "claude-3-5-sonnet-20241022",
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    if system_prompt:
                        payload["system"] = system_prompt

                    res = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload
                    )
                    if res.status_code == 200:
                        data = res.json()
                        content = data["content"][0]["text"]
                        logger.info(f"Anthropic completion generated ({len(content)} chars)")
                        return content.strip()
            except Exception as e:
                logger.warning(f"Anthropic call failed, using deterministic fallback: {e}")

        # 3. Deterministic Rule-Based Fallback
        if fallback_fn:
            if callable(fallback_fn):
                return fallback_fn()
            return str(fallback_fn)

        return "Generated response based on matching skills and structured role requirements."


llm_client = LLMClient()
