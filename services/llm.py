import base64
from pathlib import Path

from openai import AsyncOpenAI

import config

_client = None


def _get_client():
    """Lazy-initialize the OpenAI client (avoids crash on import without API key)."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


VISION_PROMPT = """You are a professional photo analysis assistant. Describe this photo in detail.

Please structure your response with the following sections:

1. **Scene Description**: What is shown in the photo? Describe the setting, objects, and overall composition.

2. **People**: If there are people visible, describe their appearance, approximate age, expression, pose, and what they are wearing.

3. **Mood & Atmosphere**: What mood or feeling does the photo convey? Describe the emotional impact.

4. **Technical Details**: Comment on lighting, colors, focus, framing, and image quality.

5. **Interesting Observations**: Any noteworthy details, surprises, or unique aspects of the photo."""


async def analyze_image(image_path: str) -> dict:
    """Analyze an image using OpenAI Vision API. Returns dict with analysis, model, usage."""

    # Read and base64-encode the image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # Detect MIME type from extension
    ext = Path(image_path).suffix.lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    response = await _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                            "detail": "low",
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
        temperature=0.7,
    )

    return {
        "analysis": response.choices[0].message.content or "",
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens
            if response.usage
            else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        },
    }
