"""
JobCopilot - Human-Likeness Physics & Biometrics Engine
Simulates authentic human interaction dynamics: Cubic Bézier mouse trajectories,
Gaussian keystroke rhythm with digraph variance, and organic page exploration.
"""

import math
import random
import asyncio
from typing import List, Tuple, Any
try:
    from playwright.async_api import Page, ElementHandle
except ImportError:
    Page = Any  # type: ignore
    ElementHandle = Any  # type: ignore


class HumanBehaviorEngine:
    """Simulates realistic human mouse dynamics and typing biomechanics."""

    @staticmethod
    def _calculate_bezier_point(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
        """Calculates a point on a cubic Bézier curve at parameter t in [0, 1]."""
        u = 1.0 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t

        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return (x, y)

    @classmethod
    def generate_mouse_path(cls, start: Tuple[float, float], end: Tuple[float, float], steps: int = 25) -> List[Tuple[float, float]]:
        """Generates a list of (x, y) coordinates along a randomized cubic Bézier curve."""
        x0, y0 = start
        x3, y3 = end

        # Randomized control points with natural deviation
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        # Deviation proportional to distance
        deviation = min(max(dist * 0.25, 20.0), 120.0)
        p1 = (x0 + dx * 0.3 + random.uniform(-deviation, deviation), y0 + dy * 0.1 + random.uniform(-deviation, deviation))
        p2 = (x0 + dx * 0.7 + random.uniform(-deviation, deviation), y0 + dy * 0.9 + random.uniform(-deviation, deviation))

        points = []
        for i in range(steps + 1):
            t = i / float(steps)
            # Apply ease-in-out easing for realistic velocity
            eased_t = t * t * (3.0 - 2.0 * t)
            pt = cls._calculate_bezier_point((x0, y0), p1, p2, (x3, y3), eased_t)
            points.append(pt)
        return points

    @classmethod
    async def move_mouse_humanlike(cls, page: Page, target_x: float, target_y: float):
        """Smoothly moves mouse to target position along a Bézier curve."""
        # Get current mouse approximation or default center
        start_x = getattr(page, "_mouse_x", 400.0)
        start_y = getattr(page, "_mouse_y", 300.0)

        path = cls.generate_mouse_path((start_x, start_y), (target_x, target_y), steps=random.randint(18, 28))
        for x, y in path:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.003, 0.010))

        setattr(page, "_mouse_x", target_x)
        setattr(page, "_mouse_y", target_y)

    @classmethod
    async def human_type(cls, page: Page, selector_or_element, text: str):
        """Types text with Gaussian rhythm, digraph speed variance, and micro-delays."""
        if isinstance(selector_or_element, str):
            await page.click(selector_or_element)
        else:
            await selector_or_element.click()

        fast_digraphs = {"th", "he", "in", "er", "an", "re", "on", "at", "en", "nd", "ti", "es", "or", "te", "of"}

        for i, char in enumerate(text):
            # Base typing delay (Gaussian mean=85ms, std=22ms)
            delay = random.gauss(0.085, 0.022)
            
            # Check fast digraphs
            if i > 0 and text[i-1:i+1].lower() in fast_digraphs:
                delay *= 0.65  # 35% faster for muscle memory digraphs
            elif char.isupper() or char in "!@#$%^&*()_+{}[]:\"<>?":
                delay *= 1.40  # Slower for shift / symbols

            delay = max(0.025, min(delay, 0.280))  # Clamp
            await page.keyboard.type(char)
            await asyncio.sleep(delay)

            # 1.5% chance of simulated typo and backspace correction
            if random.random() < 0.015 and char.isalpha():
                typo_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await page.keyboard.type(typo_char)
                await asyncio.sleep(random.uniform(0.12, 0.22))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.15))

    @classmethod
    async def natural_scroll_and_pause(cls, page: Page, min_pause: float = 0.4, max_pause: float = 1.2):
        """Simulates natural eye-movement pauses and subtle exploratory scrolling."""
        scroll_amount = random.randint(150, 450)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(min_pause, max_pause))
