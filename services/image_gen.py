"""DALL-E 3 image generation with prompt assembly and thumbnail compression."""
import asyncio
import uuid
from pathlib import Path

from PIL import Image
from openai import AsyncOpenAI

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
    return _client


SYSTEM_PROMPT = """你是专业的虚拟试衣时尚造型师和照片级图像生成器。你需要将指定的穿搭风格精确呈现，同时严格保持人物身份不变。

核心原则：
- 三层身份锁定：面部结构零容忍、发型发色不变、体型骨架一致
- 否定式约束优先：明确禁止美颜、瘦脸、大眼、磨皮等任何面部修改
- 变量隔离：只改变服装和背景，人物本身是常量
- 面料物理真实：服装应有自然的垂坠、褶皱、张力，而非贴图感"""

# ── Identity lock constraints (from Prompt Engine) ────────────────────

IDENTITY_LOCK = """
## 人物身份锁定（最高优先级）

### 面部结构 — 零容忍
- 眼睛形状、眼型、眼距必须与参考照片完全一致
- 鼻子：鼻梁高度、鼻尖形状、鼻翼宽度与参考完全相同
- 嘴唇：厚度、自然唇形、唇色与参考完全相同
- 下颌线、下巴、颧骨与参考完全相同
- 肤色必须完全一致，不可提亮或加深
- 皮肤纹理保留：毛孔、雀斑、痣等自然特征不可磨除
- 年龄不可改变（不变年轻、不变老）
- 种族特征不可偏移

### 发型发色 — 不变
- 发色保持参考照片的自然色
- 长度不变（允许微调造型，但发型长度须可辨识）
- 发质不变（直发保持直发、卷发保持卷发）

### 体型 — 一致
- 肩宽、躯干长度、胯宽不变
- 身高印象不变
- 不可瘦身、增肌或美化体型

## 绝对禁止
1. 禁止任何面部特征修改
2. 禁止磨皮或"美颜滤镜"效果
3. 禁止肤色美白或变暗
4. 禁止改变瞳色
5. 禁止修改脸型（禁止瘦脸、禁止加宽）
6. 禁止将人物画成"模特"——必须像他们自己
7. 禁止插图、绘画、动漫、风格化渲染——严格照片级写实
8. 禁止把面部贴到另一个身体上——身体必须匹配参考人物的骨架
9. 禁止添加参考中不存在的酒窝/双眼皮/痣
10. 禁止改变年龄
"""

FABRIC_PHYSICS = """
## 服装物理真实感要求
- 面料应有自然的垂坠、褶皱、张力
- 外套应靠自重垂落和折叠
- 牛仔裤在踝部应有微小的堆积感
- 毛衣应有自然的蓬松和柔软度
- 服装必须与身体产生交互——不能像贴上去的
- 纽扣、拉链的比例必须正确
"""

COMPOSITION = """
## 构图参数
- 比例: 3:4 竖版
- 取景: 全身照（头顶到脚底完整可见）
- 背景: 纯色无缝影棚幕布，暖灰白色调，无纹理，无渐变
- 光线: 柔和漫射影棚光，45° 上方打光，面光清晰
- 表现: 自然放松，穿着舒适感，不刻意摆拍
"""


def build_prompt(
    height: float,
    weight: float,
    bust: float | None,
    waist: float | None,
    hip: float | None,
    text: str | None,
    clothing_tags: list[str] | None,
    style_tags: list[str] | None,
    scene_tags: list[str] | None,
    has_user_photo: bool,
    has_reference: bool,
) -> str:
    """Assemble a professional-grade fashion generation prompt."""

    sections = [SYSTEM_PROMPT]

    # ═══ Identity Lock ═══
    if has_user_photo:
        sections.append("""
## 参考照片说明
用户提供了自己的真实照片作为身份参考。请仔细研究照片中人物的面部特征、发型、体型。
以下身份锁定约束必须严格遵守：""")
        sections.append(IDENTITY_LOCK)
    else:
        sections.append("""
## 人物参考
用户未提供照片。请根据以下身体数据生成一位符合描述的人物，并保持面部特征在多次生成中一致。""")

    # ═══ Body Data ═══
    body_parts = []
    if height and height > 0:
        body_parts.append(f"身高 {height}cm")
    if weight and weight > 0:
        body_parts.append(f"体重 {weight}kg")
    if bust:
        body_parts.append(f"胸围 {bust}cm")
    if waist:
        body_parts.append(f"腰围 {waist}cm")
    if hip:
        body_parts.append(f"臀围 {hip}cm")
    if body_parts:
        sections.append("## 用户身体数据\n" + "，".join(body_parts) + "。")

    # ═══ Style Specification ═══
    sections.append("## 穿搭需求")

    spec_parts = []
    if clothing_tags:
        spec_parts.append(f"衣服款式：{'、'.join(clothing_tags)}")
    if style_tags:
        spec_parts.append(f"风格偏好：{'、'.join(style_tags)}")
    if scene_tags:
        spec_parts.append(f"穿着场景：{'、'.join(scene_tags)}")
    if text:
        spec_parts.append(f"用户描述：{text}")

    if spec_parts:
        sections.append("。\n".join(spec_parts) + "。")

    # ═══ Reference Images ═══
    if has_reference:
        sections.append("""
## 服装参考图
用户提供了服装参考图。请参考其中的风格、款式、配色和搭配方式，但必须将服装穿在目标人物身上（而非参考图中的人）。""")

    # ═══ Quality Controls ═══
    sections.append(FABRIC_PHYSICS)
    sections.append(COMPOSITION)

    # ═══ Final instruction ═══
    sections.append("""
## 最终检查
生成前请确认：
- 遮住衣服只看脸，能认出是同一个人吗？
- 衣服看起来真的穿在身上吗（有褶皱、张力、阴影交互）？
- 有没有不小心美化、磨皮或修改了面部？
- 光线在面部、身体和背景上一致吗？
任一答案为否 → 重新生成。""")

    return "\n".join(sections)


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


async def generate_image(
    prompt: str,
    size: str = "1024x1024",
) -> dict:
    """Call image generation API. Supports both official (url) and relay (b64_json) responses."""

    response = await _get_client().images.generate(
        model=config.OPENAI_MODEL,
        prompt=prompt,
        size=size,
        quality=config.IMAGE_QUALITY,
        n=1,
    )

    data = response.data[0]

    # Official API returns url, relay APIs often return b64_json
    if data.url:
        return {
            "image_url": data.url,
            "revised_prompt": data.revised_prompt or prompt,
        }

    if data.b64_json:
        # Decode base64 and save locally
        import base64 as b64
        filename = f"{uuid.uuid4()}.png"
        file_path = config.UPLOAD_DIR / filename
        with open(file_path, "wb") as f:
            f.write(b64.b64decode(data.b64_json))
        return {
            "image_url": f"/api/uploads/{filename}",
            "revised_prompt": data.revised_prompt or prompt,
        }

    raise Exception("API 返回的图片数据既没有 url 也没有 b64_json")
