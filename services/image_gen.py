"""GPT Image 2 generation with PromptEngine assembly and thumbnail compression."""
import asyncio
import base64
import uuid
from pathlib import Path

import aiofiles
import httpx
from PIL import Image
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


DEFAULT_COMPOSITION = """\
---COMPOSITION PARAMETERS---
Aspect Ratio: 3:4 vertical
Framing: Full body from head to toe
Background: Seamless warm off-white studio backdrop, no texture, no gradient
Lighting: Soft diffused studio light, 45° above eye level, clear facial modeling
Pose: Natural relaxed standing pose, wearing comfort visible
Quality: Photorealistic fashion editorial, 4K-level facial detail, natural fabric drape
---END COMPOSITION PARAMETERS---"""


def build_final_prompt(
    identity_features: str,
    style_directive: str,
    composition_settings: str = DEFAULT_COMPOSITION,
) -> str:
    """Render the final style-transfer prompt via PromptEngine."""
    engine = PromptEngine()
    return engine.render_style_transfer(
        identity_features=identity_features,
        style_directive=style_directive,
        composition_settings=composition_settings,
    )


def _compress_image_sync(
    input_path: str,
    max_width: int = 600,
    quality: int = 60,
) -> str:
    """Synchronous PIL resize+compress. Called via asyncio.to_thread."""
    thumb_name = f"{uuid.uuid4()}_thumb.jpg"
    thumb_path = config.UPLOAD_DIR / thumb_name

    img = Image.open(input_path)
    img = img.convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    img.save(thumb_path, "JPEG", quality=quality, optimize=True)
    return thumb_name


async def compress_image(
    input_path: str,
    max_width: int = 600,
    quality: int = 60,
) -> str:
    """Async wrapper: calls sync PIL code in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_compress_image_sync, input_path, max_width, quality)


async def _save_generation_result(data, prompt: str, prefix: str = "") -> dict:
    """Persist image returned by OpenAI Images API to local disk.

    Returns dict with keys:
        - image_url: local /api/uploads/... path or remote URL
        - local_path: absolute filesystem path (if saved locally)
        - revised_prompt: str
    """
    revised = data.revised_prompt or prompt

    if data.url:
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(data.url)
            resp.raise_for_status()
        filename = f"{prefix}{uuid.uuid4()}.png"
        file_path = config.UPLOAD_DIR / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(resp.content)
        return {
            "image_url": f"/api/uploads/{filename}",
            "local_path": str(file_path),
            "revised_prompt": revised,
        }

    if data.b64_json:
        filename = f"{prefix}{uuid.uuid4()}.png"
        file_path = config.UPLOAD_DIR / filename
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(data.b64_json))
        return {
            "image_url": f"/api/uploads/{filename}",
            "local_path": str(file_path),
            "revised_prompt": revised,
        }

    raise Exception("API 返回的图片数据既没有 url 也没有 b64_json")


# ── Step 1: Standard Portrait ──────────────────────────────────────────

async def generate_standard_portrait(identity_features: str) -> dict:
    """Generate a neutral base portrait from identity text features.

    Uses images.generate (text-to-image) because we have no visual reference yet.
    """
    engine = PromptEngine()
    prompt = engine.render_standard_portrait(identity_features)

    response = await _get_client().images.generate(
        model=config.OPENAI_MODEL,
        prompt=prompt,
        size=config.IMAGE_SIZE,
        quality=config.IMAGE_QUALITY,
        n=1,
    )

    return await _save_generation_result(
        response.data[0], prompt, prefix="standard_"
    )


# ── Step 2: Style Transfer with Reference ──────────────────────────────

async def generate_styled_image(
    prompt: str,
    reference_image_path: str,
) -> dict:
    """Generate styled outfit image using a reference portrait via images.edit.

    Uses images.edit so the model can see the reference person's face/body.
    NOTE: images.edit does NOT accept 'quality' parameter for gpt-image-1.
    """
    with open(reference_image_path, "rb") as img_file:
        response = await _get_client().images.edit(
            image=img_file,
            prompt=prompt,
            model=config.OPENAI_MODEL,
            size=config.IMAGE_SIZE,
            n=1,
        )

    return await _save_generation_result(response.data[0], prompt)


# ── Fallback: text-only generation (no reference photo) ────────────────

async def generate_image(
    prompt: str,
) -> dict:
    """Call GPT Image 2 via the OpenAI-compatible images.generations endpoint.

    Fallback for cases where no user photo was uploaded and we have no
    standard portrait to use as reference.
    """
    response = await _get_client().images.generate(
        model=config.OPENAI_MODEL,
        prompt=prompt,
        size=config.IMAGE_SIZE,
        quality=config.IMAGE_QUALITY,
        n=1,
    )

    return await _save_generation_result(response.data[0], prompt)
