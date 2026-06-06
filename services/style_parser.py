"""GPT-4o Text parser: translate user tags + text into a structured styling brief."""
from openai import AsyncOpenAI

import config
from services.prompt_engine import PromptEngine

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
    return _client


async def parse_style(
    raw_text: str,
    tags: list[str] | None = None,
    gender_hint: str = "neutral",
    season_hint: str = "none",
    occasion_hint: str = "none",
    identity_features: str = "",
    clothing_analysis: str | None = None,
) -> str:
    """Call GPT-4o to produce a structured styling brief.

    If identity_features / clothing_analysis are provided, they are added as
    additional context so the stylist can adapt recommendations to the user.
    """
    engine = PromptEngine()
    parser_prompt = engine.parse_style(
        raw_text=raw_text,
        tags=tags or [],
        gender_hint=gender_hint,  # type: ignore[arg-type]
        season_hint=season_hint,  # type: ignore[arg-type]
        occasion_hint=occasion_hint,  # type: ignore[arg-type]
    )

    extra_context = ""
    if identity_features:
        extra_context += f"""
## USER IDENTITY CONTEXT (for fit and adaptation only)
{identity_features}
"""
    if clothing_analysis:
        extra_context += f"""
## REFERENCE OUTFIT CONTEXT
{clothing_analysis}
"""

    if extra_context:
        parser_prompt += (
            "\n\nUse the following additional context to make the styling brief "
            "more accurate for this specific person and reference outfit:\n"
            + extra_context
        )

    client = _get_client()
    response = await client.chat.completions.create(
        model=config.OPENAI_TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a senior fashion director. Respond ONLY in the requested structured format.",
            },
            {"role": "user", "content": parser_prompt},
        ],
        max_completion_tokens=2048,
        temperature=0.5,
    )

    return response.choices[0].message.content or ""
