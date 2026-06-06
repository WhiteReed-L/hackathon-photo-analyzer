"""GPT-4o Text parser: translate user tags + text into a structured styling brief."""
import json

import config
from services.ai_client import default_client
from services.prompt_engine import PromptEngine


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

    client = default_client()
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


def _extract_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                return None
    return None


def style_brief_to_directive(brief: dict) -> str:
    """Render structured styling brief JSON back to the legacy directive text."""
    def garment_text(key: str) -> str:
        item = brief.get(key) or {}
        if isinstance(item, str):
            return item
        if not isinstance(item, dict):
            return "none"
        parts = [item.get(k) for k in ("type", "style", "color", "material", "fit", "details") if item.get(k)]
        return "，".join(parts) if parts else "none"

    colors = brief.get("color_palette") or brief.get("colors") or []
    materials = brief.get("materials") or []
    accessories = brief.get("accessories") or []
    if isinstance(accessories, list):
        accessories_text = "，".join(str(a) for a in accessories) or "none"
    else:
        accessories_text = str(accessories)
    return "\n".join([
        "---STYLING BRIEF---",
        f"Style Name: {brief.get('style_name') or brief.get('overall_style') or '穿搭方案'}",
        f"Overall Mood: {brief.get('overall_mood') or brief.get('mood') or ''}",
        f"Top Garment: {garment_text('top_garment')}",
        f"Bottom Garment: {garment_text('bottom_garment')}",
        f"Footwear: {garment_text('footwear')}",
        f"Accessories: {accessories_text}",
        f"Color Palette: {'，'.join(colors) if isinstance(colors, list) else colors}",
        f"Materials & Textures: {'，'.join(materials) if isinstance(materials, list) else materials}",
        f"Silhouette: {brief.get('silhouette') or ''}",
        f"Styling Notes: {brief.get('styling_notes') or ''}",
        "---END STYLING BRIEF---",
    ])


def _fallback_structured_from_text(text: str) -> dict:
    parsed = PromptEngine.parse_styling_brief(text)
    return {
        "style_name": parsed.get("Style Name") or "穿搭方案",
        "top_garment": {"style": parsed.get("Top Garment", "")},
        "bottom_garment": {"style": parsed.get("Bottom Garment", "")},
        "footwear": {"style": parsed.get("Footwear", "")},
        "accessories": [parsed.get("Accessories", "")],
        "color_palette": [c.strip() for c in parsed.get("Color Palette", "").replace("、", ",").split(",") if c.strip()],
        "materials": [m.strip() for m in parsed.get("Materials & Textures", "").replace("、", ",").split(",") if m.strip()],
        "silhouette": parsed.get("Silhouette", ""),
        "styling_notes": parsed.get("Styling Notes", ""),
    }


async def parse_style_structured(*args, **kwargs) -> tuple[str, dict]:
    raw = await parse_style(*args, **kwargs)
    data = _extract_json(raw)
    if not data:
        data = _fallback_structured_from_text(raw)
    return style_brief_to_directive(data), data
