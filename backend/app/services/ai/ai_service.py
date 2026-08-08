"""
AIService abstraction.

Every AI-driven feature in this codebase (company generation flavor text,
project generation, and — in later phases — the AI Project Manager and AI
teammates chat) talks to this interface, never to Gemini directly. That
means:

  - Today, with no GEMINI_API_KEY set, MockAIService produces deterministic,
    still-varied, still-real output (no external calls, nothing "fake" in
    the sense of broken — it's a legitimate rule-based generator).
  - The moment GEMINI_API_KEY is set in the environment, get_ai_service()
    starts returning GeminiAIService instead, with zero call-site changes.

This is the abstraction FEATURE 6 (AI Project Manager) and FEATURE 7
(AI Teammates) will build on in the next phase.
"""
import json
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class AIService(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Return a free-form text completion."""
        raise NotImplementedError

    @abstractmethod
    async def generate_json(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return a completion parsed as JSON. Caller defines the expected shape."""
        raise NotImplementedError


import re


class MockAIService(AIService):
    """
    Deterministic-but-varied rule-based provider. Used automatically whenever
    GEMINI_API_KEY is empty, so the whole engine is fully runnable with zero
    external dependencies or API keys.
    """

    _MISSION_TEMPLATES = [
        "To {verb} {domain} through relentless focus on {value}.",
        "Empowering {audience} by {verb_ing} {domain} at scale.",
        "Building the future of {domain} — one {value}-driven release at a time.",
    ]
    _VERBS = ["transform", "simplify", "reinvent", "accelerate", "modernize"]
    _VALUES = ["quality", "customer trust", "engineering excellence", "innovation", "reliability"]
    _AUDIENCES = ["businesses", "developers", "patients", "learners", "consumers", "enterprises"]

    _MANAGER_REPLIES = {
        "strict": [
            "Noted. {stress_clause}Keep the pace up — {sprint_clause}",
            "Fine, but I expect this closed out properly. {deadline_clause}",
            "Good. Don't let it slip like the last {missed} missed deadline(s) did.",
        ],
        "friendly": [
            "Thanks for the update! {stress_clause}You're doing solid work — {sprint_clause}",
            "Appreciate you flagging that. {deadline_clause} Let me know if you're stuck on anything.",
            "Nice progress so far — {completed} tasks down. Keep it up!",
        ],
        "corporate": [
            "Understood. Let's ensure this stays aligned with our sprint {sprint_num} objectives.",
            "Thank you for the visibility. {deadline_clause} I'll loop in stakeholders as needed.",
            "Acknowledged. Current velocity shows {completed} tasks completed — on track overall.",
        ],
        "startup_founder": [
            "Love it, let's ship it. {sprint_clause}",
            "Keep moving — {completed} down, more to go. We don't slow down here.",
            "Cool cool. {deadline_clause} Momentum is everything right now.",
        ],
    }

    _TEAMMATE_REPLIES = [
        "Got it — I'll take a look and circle back with what I find.",
        "Makes sense. Want me to pair on this or are you good solo?",
        "Heads up, I hit something similar last sprint — happy to compare notes.",
        "Nice, that unblocks me too. Thanks for the update.",
        "I can review that once it's up — just tag me.",
    ]

    def _extract_int(self, text: str, key: str, default: int = 0) -> int:
        match = re.search(rf"{key}=(\-?\d+)", text)
        return int(match.group(1)) if match else default

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        sp = system_prompt or ""

        # Manager chat context (see app/services/ai_manager.py)
        if "the manager on project" in sp:
            rng = random.Random(hash(prompt) & 0xFFFFFFFF)
            personality = "corporate"
            for key in self._MANAGER_REPLIES:
                if key.replace("_", " ") in sp.lower() or key in sp.lower():
                    personality = key
                    break
            missed = self._extract_int(prompt, "missed_deadlines")
            completed = self._extract_int(prompt, "completed_tasks")
            stress = self._extract_int(prompt, "stress_level")
            sprint_num = self._extract_int(prompt, "current_sprint")

            template = rng.choice(self._MANAGER_REPLIES[personality])
            return template.format(
                stress_clause="I can tell things are getting intense. " if stress >= 60 else "",
                deadline_clause=(
                    f"We've missed {missed} deadline(s) so far — let's not add to that."
                    if missed > 0
                    else "Deadlines are holding steady, which is good."
                ),
                sprint_clause=f"we're in sprint {sprint_num} of 4, stay focused.",
                missed=missed,
                completed=completed,
                sprint_num=sprint_num,
            )

        # AI teammate chat context (see app/services/ai_teammates.py)
        if "teammate" in sp.lower() and "messaging" in sp.lower():
            rng = random.Random(hash(prompt) & 0xFFFFFFFF)
            return rng.choice(self._TEAMMATE_REPLIES)

        # Default: company mission/description flavor text generation.
        rng = random.Random(hash(prompt) & 0xFFFFFFFF)
        template = rng.choice(self._MISSION_TEMPLATES)
        return template.format(
            verb=rng.choice(self._VERBS),
            verb_ing=rng.choice(self._VERBS) + "ing",
            domain=self._extract_domain(prompt),
            value=rng.choice(self._VALUES),
            audience=rng.choice(self._AUDIENCES),
        )

    async def generate_json(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        # The mock provider is only used for free-text flavor fields in this
        # phase; structured generation (project objectives/modules/etc.) is
        # handled by the template-based generators directly for reliability.
        text = await self.generate_text(prompt, system_prompt)
        return {"text": text}

    @staticmethod
    def _extract_domain(prompt: str) -> str:
        lowered = prompt.lower()
        for keyword in [
            "healthcare", "banking", "e-commerce", "ecommerce", "education",
            "logistics", "retail", "fintech", "manufacturing",
        ]:
            if keyword in lowered:
                return keyword
        return "technology"


class GeminiAIService(AIService):
    """Real Gemini-backed implementation, used once GEMINI_API_KEY is configured."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

    async def _call(self, prompt: str, system_prompt: Optional[str]) -> str:
        contents: List[Dict[str, Any]] = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}?key={self.api_key}",
                json={"contents": contents},
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return await self._call(prompt, system_prompt)

    async def generate_json(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        json_instruction = (
            "Respond ONLY with valid JSON. No markdown fences, no preamble, no commentary."
        )
        full_system = f"{system_prompt}\n{json_instruction}" if system_prompt else json_instruction
        raw = await self._call(prompt, full_system)
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)


def get_ai_service() -> AIService:
    if settings.GEMINI_API_KEY:
        return GeminiAIService(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    return MockAIService()
