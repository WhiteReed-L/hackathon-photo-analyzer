"""
Prompt Engine — AI Virtual Fitting Room
========================================

将所有 Prompt 模板集中管理，提供参数化渲染接口。
后端只需实例化 PromptEngine，调用对应方法即可获取完整 Prompt 文本。

文件位置: services/prompt_engine.py (建议)
"""

from typing import Literal


class PromptEngine:
    """
    Prompt 模板引擎。

    负责渲染 4 个核心 Prompt：
    1. extract_identity()     -> Step 0: 身份特征提取
    2. render_standard()      -> Step 1: 标准人像生成
    3. parse_style()          -> Step 3: 风格解析
    4. render_styled()        -> Step 2: 风格换装生成

    所有模板均支持纯字符串拼接，不依赖任何外部库。
    """

    # ============================================================
    # Step 0: Identity Extraction
    # ============================================================

    IDENTITY_EXTRACTION_PROMPT: str = """\
You are a forensic facial analysis system. Analyze the person in the provided
image and extract a comprehensive, objective identity profile.

## EXTRACTION RULES

### INCLUDE (Stable Physical Traits)
- Gender presentation and apparent sex
- Apparent age range (decade-level precision: "early 20s", "mid 30s", "late teens")
- Ethnicity and skin tone (Fitzpatrick scale reference + descriptive term)
- Face shape (oval, round, square, heart, diamond, oblong, triangular)
- Forehead height and width proportion
- Eyebrow characteristics (thickness, arch, color, shape)
- Eye features (shape, eyelid type, spacing, size relative to face)
- Nose structure (bridge height, width, tip shape, nostril visibility)
- Lips (fullness, shape, natural color tone)
- Jawline and chin (defined/soft, squared/rounded, presence of cleft)
- Cheekbones (prominent/average/flat, width)
- Ears (size, attachment, visibility)
- Hairstyle (exact length, texture, parting, volume, layering)
- Hair color (natural base color, any visible highlights/graying)
- Facial hair (if applicable: type, density, coverage area)
- Build/body type (frame size, approximate proportions, visible posture traits)
- Height impression (tall/average/petite relative to frame)
- Distinguishing marks (moles, freckles, scars, birthmarks, glasses, braces)

### EXCLUDE (Variable/Non-Physical Traits)
- Clothing, accessories, jewelry
- Facial expression (smile, frown, neutral — do NOT describe)
- Makeup or grooming beyond permanent features
- Pose, angle, or body orientation
- Background or environmental context
- Lighting effects on skin appearance
- Emotional state or personality inferences

## OUTPUT FORMAT

Respond ONLY in the following structured format. Do NOT add conversational text.

---IDENTITY PROFILE BEGIN---
GENDER: [value]
AGE_RANGE: [value]
ETHNICITY: [value]
SKIN_TONE_FITZPATRICK: [I-VI]
SKIN_TONE_DESC: [value]
FACE_SHAPE: [value]
FOREHEAD: [value]
EYEBROWS: [value]
EYES_SHAPE: [value]
EYES_EYELID: [single/double/hooded/monolid/deep-set]
EYES_SPACING: [close-set/average/wide-set]
NOSE_BRIDGE: [value]
NOSE_TIP: [value]
NOSE_WIDTH: [value]
LIPS_FULLNESS: [thin/average/full]
LIPS_SHAPE: [value]
JAWLINE: [value]
CHIN: [value]
CHEEKBONES: [value]
EARS: [value]
HAIR_LENGTH: [value]
HAIR_TEXTURE: [straight/wavy/curly/coily/kinky]
HAIR_STYLE: [value]
HAIR_PARTING: [left/right/center/none]
HAIR_COLOR_BASE: [value]
HAIR_COLOR_HIGHLIGHTS: [value OR "none visible"]
FACIAL_HAIR: [value OR "none"]
BUILD_FRAME: [slim/athletic/average/heavyset/petite]
BUILD_SHOULDERS: [narrow/average/broad]
BUILD_TORSO: [long/average/short]
BUILD_PROPORTIONS: [value]
HEIGHT_IMPRESSION: [value]
DISTINGUISHING_MARKS: [comma-separated list OR "none visible"]
GLASSES: [yes/no, if yes describe frames]
OVERALL_SIGNATURE: [2-3 sentences of distinctive visual identifiers]
---IDENTITY PROFILE END---

## ACCURACY GUIDELINES

- If a feature is unclear due to image quality or angle, state "NOT CLEARLY VISIBLE"
  rather than guessing.
- For skin tone, provide both Fitzpatrick scale (I-VI) and a descriptive term
  (e.g., "warm beige", "deep espresso", "porcelain with cool undertones").
- For hairstyle, be precise about length relative to anatomy:
  "ear-length", "chin-length", "shoulder-length", "mid-back", etc.
- For body type, focus on FRAME (bone structure) rather than weight.
- "Overall Signature" should capture the 2-3 most distinctive visual traits that
  would allow a stranger to pick this person out of a lineup.
"""

    def extract_identity(self) -> str:
        """
        返回 Step 0 的完整 Prompt。

        调用方式:
            prompt = engine.extract_identity()
            response = call_gpt4o_vision(prompt, image_base64=user_photo)
        """
        return self.IDENTITY_EXTRACTION_PROMPT

    # ============================================================
    # Step 1: Standard Portrait Generation
    # ============================================================

    STANDARD_PORTRAIT_TEMPLATE: str = """\
You are generating a standardized neutral base portrait for virtual fashion
styling purposes. This image will be used as a reference for subsequent
clothing changes, so facial and bodily accuracy is CRITICAL.

## REFERENCE INPUT

Use the provided reference photograph to identify the person.

## IDENTITY ANCHOR (MUST PRESERVE WITH 100% FIDELITY)

{identity_features}

## GENERATION SPECIFICATION

### Subject
The EXACT same person from the reference photo, rendered as a full-body
photograph.

### Clothing (NEUTRAL BASE LAYER)
- Top: Plain white crew-neck t-shirt, short sleeves, no logos, no patterns,
  no text, fitted but not tight
- Bottom: Fitted black straight-leg trousers, mid-rise, no belt, no pleats,
  minimal detail, clean hem
- Footwear: Plain white low-top canvas sneakers, no visible branding
- Accessories: NONE. No watches, no rings, no necklaces, no earrings,
  no bracelets, no glasses (unless medically necessary per identity profile)

### Pose
- Standing upright, facing directly toward camera
- Feet shoulder-width apart, weight evenly distributed
- Arms relaxed at sides, hands naturally open
- Shoulders level, spine straight
- Head facing forward, gaze directed at camera lens
- Full body visible from top of head to bottom of feet

### Expression
- Neutral, relaxed facial expression
- Mouth closed in natural rest position (not pursed, not open)
- Eyes open, looking directly at camera
- No smile, no frown, no raised eyebrows
- "Passport photo" level of neutrality

### Environment
- Background: Seamless light gray studio backdrop (RGB approximately #D3D3D3)
- Floor: Slightly darker gray seamless surface, subtle shadow beneath feet
- No furniture, no props, no text, no logos, no environmental context

### Lighting
- Primary: Soft, even, frontal key light at approximately 45° above eye level
- Fill: Gentle fill light from below to minimize under-chin shadows
- No colored gels, no dramatic shadows, no rim light, no backlight
- Goal: Reveal ALL facial features clearly for subsequent identification

### Camera Specification
- Angle: Eye-level, straight-on (no high angle, no low angle)
- Lens: 50mm equivalent perspective (minimal distortion)
- Distance: Full body in frame with approximately 10% headroom above head
- Focus: Sharp focus on face, adequate depth for full body

## CRITICAL CONSTRAINTS (STRICT MODE — HIGHEST PRIORITY)

1. FACIAL IDENTITY — ABSOLUTE
   - The face MUST be the exact same individual from the reference photo
   - Preserve: eye shape, eyelid type, eye spacing, eyebrow shape and thickness
   - Preserve: nose bridge height, nose tip shape, nose width, nostril shape
   - Preserve: lip fullness, lip shape, natural lip color tone
   - Preserve: jawline definition, chin shape, cheekbone prominence
   - Preserve: exact skin tone and skin texture (including freckles, moles,
     visible pores if present in reference)
   - Preserve: apparent age — do NOT make younger or older
   - Preserve: ethnicity presentation

2. HAIR — UNCHANGED
   - Exact same hair color as reference (natural base color)
   - Exact same hair length as reference
   - Exact same hair texture as reference (straight/wavy/curly)
   - Hairstyle should be in its natural state — not styled up, not gelled,
     not blow-dried. Natural fall.

3. BODY — CONSISTENT
   - Same body frame, same shoulder width, same torso length
   - Same height impression
   - Same posture tendencies (if reference shows slight slouch, maintain slight
     slouch; if very upright, maintain upright)
   - Do NOT idealize physique. If reference shows average build, maintain
     average build. Do NOT add muscle definition that isn't there.

4. ABSOLUTE PROHIBITIONS
   - NO skin smoothing or beautification
   - NO face slimming or jawline sharpening
   - NO eye enlargement
   - NO skin tone lightening or darkening
   - NO age modification
   - NO addition of makeup
   - NO change to facial proportions
   - NO "idealized" or "glamour" treatment
   - This is a DOCUMENTARY reference image, not a portrait for social media

## QUALITY SPECIFICATION

- Photorealistic, not illustrated or painted
- Fashion editorial standard sharpness
- 4K-level detail in facial features
- Natural fabric drape on the neutral clothing
- Believable skin texture (not plastic or porcelain)
- Professional studio photography aesthetic
"""

    def render_standard_portrait(self, identity_features: str) -> str:
        """
        渲染 Step 1 标准人像生成 Prompt。

        Args:
            identity_features: Step 0 输出的完整身份特征文本

        Returns:
            可直接传给 OpenAI 图像生成 API 的完整 Prompt
        """
        return self.STANDARD_PORTRAIT_TEMPLATE.format(
            identity_features=identity_features.strip()
        )

    # ============================================================
    # Step 3: Style Parser
    # ============================================================

    STYLE_PARSER_TEMPLATE: str = """\
You are a senior fashion director at a top-tier styling agency. Your job is
to translate client requests into precise, executable styling briefs for
AI-generated fashion photography.

## INPUT

Client's text description: "{raw_text}"

Selected style tags: {tags}

Client profile:
- Gender presentation: {gender_hint}
- Season context (if any): {season_hint}
- Occasion context (if any): {occasion_hint}

## YOUR TASK

Convert the client's request into a structured styling brief. This brief will
be fed directly into an AI image generator to create a fashion portrait.
Therefore, your output must be VISUALLY PRECISE and ACTIONABLE.

## CRITICAL RULES

1. FOCUS ON CLOTHING ONLY
   - Describe garments, accessories, footwear, fabrics, colors, cuts
   - Do NOT describe face, body, expression, or personality
   - Do NOT reference celebrities or models as "inspiration"
   - Do NOT use subjective evaluative language ("elegant", "sexy", "cute")
   - Use MATERIAL and STRUCTURAL descriptors instead

2. BE SPECIFIC, NOT VAGUE
   - ❌ "nice coat" -> ✅ "mid-thigh length wool-cashmere coat, raglan
        sleeves, concealed button placket, in charcoal gray"
   - ❌ "cool shoes" -> ✅ "black leather combat boots, matte finish,
        8-eyelet lace-up, chunky rubber sole"
   - ❌ "pretty colors" -> ✅ "dusty rose, ivory, and soft taupe palette"

3. RESOLVE AMBIGUITY CONFIDENTLY
   - If the client is vague, make an EDITORIAL CHOICE rather than asking
     for clarification
   - Choose the MOST DEFINITIVE version of the requested style

4. HANDLE CONTRADICTORY INPUT
   - If tags and text conflict, prioritize the TEXT as the primary intent
     and use tags as secondary guidance
   - Attempt to SYNTHESIZE rather than choose one

5. SEASON AND OCCASION AWARENESS
   - Apply seasonal logic even if not explicitly stated
   - Apply occasion logic to determine formality and coverage

6. GENDER ADAPTATION (Without Stereotyping)
   - Use the gender_hint as a FIT starting point, not a restriction
   - NEVER exclude a style based on gender — adapt the cut and fit instead

## OUTPUT FORMAT

Respond ONLY in the following format. No conversational text.

---STYLING BRIEF---
Style Name: [2-4 words, evocative but clear]
Overall Mood: [1 sentence capturing the emotional/atmospheric quality]

Top Garment: [specific upper body garment with construction details]
Bottom Garment: [specific lower body garment with construction details]
Footwear: [specific shoes with material and style details]
Accessories: [specific items OR "none" — be explicit]

Color Palette: [3-5 colors, each with shade descriptor]
Materials & Textures: [key fabrics and their tactile qualities]
Silhouette: [overall shape — e.g., "structured top / relaxed bottom",
            "columnar and flowing", "boxy throughout"]

Era/Region Reference: [fashion context if applicable]

Styling Notes: [2-3 sentences on how pieces relate to each other, what
               styling technique creates the intended effect]

Background Vibe: [brief scene suggestion that matches the style mood]
---END STYLING BRIEF---
"""

    def parse_style(
        self,
        raw_text: str,
        tags: list[str],
        gender_hint: Literal["male", "female", "neutral"] = "neutral",
        season_hint: Literal["spring", "summer", "autumn", "winter", "none"] = "none",
        occasion_hint: Literal["daily", "work", "date", "party", "outdoor", "travel", "none"] = "none",
    ) -> str:
        """
        渲染 Step 3 风格解析 Prompt。

        Args:
            raw_text: 用户自由输入的风格描述
            tags: 前端勾选的快捷标签列表
            gender_hint: 从身份特征推断的性别倾向
            season_hint: 季节上下文
            occasion_hint: 场合上下文

        Returns:
            传给 GPT-4o Text 的完整 Prompt，输出为结构化 Styling Brief
        """
        tags_str = ", ".join(tags) if tags else "none"
        return self.STYLE_PARSER_TEMPLATE.format(
            raw_text=raw_text.strip(),
            tags=tags_str,
            gender_hint=gender_hint,
            season_hint=season_hint,
            occasion_hint=occasion_hint,
        )

    # ============================================================
    # Step 2: Style Transfer (Final Styled Image)
    # ============================================================

    STYLE_TRANSFER_TEMPLATE: str = """\
You are a professional virtual fashion stylist. Your task is to modify the
provided photograph to change ONLY the person's clothing while preserving
their identity, pose, and environment perfectly.

## PRIMARY REFERENCE

### The Person in This Photo
The provided image is the user's OWN PHOTOGRAPH. This is the actual person
you are styling. Preserve their face, body, hair, skin, pose, and all
physical identity features with 100% fidelity.

You are ONLY changing their clothing, accessories, and footwear — everything
else (face, hair, body shape, skin, background, lighting, pose) stays
EXACTLY as it appears in the original photo.

### Identity Anchor (for verification)
{identity_features}

## STYLE SPECIFICATION (What to Dress Them In)

{style_directive}

## COMPOSITION PARAMETERS

{composition_settings}

## EDITING INSTRUCTIONS

Modify the original photo so the person is now wearing the outfit described
in the Style Specification. This is a CLOTHING SWAP operation on a real
photograph — NOT a full regeneration of the image.

### What TO Change (ONLY These)
- Clothing: Replace current garments with those in the Style Specification
- Footwear: Replace with style-appropriate shoes
- Accessories: Add/replace as specified (or remove if "none" specified)
- Minor lighting adjustments to make new clothing look natural in the scene

### What MUST NOT Change (ABSOLUTE LOCK)

#### 1. FACE — ZERO TOLERANCE
- Every facial feature must remain pixel-identical to the input photo
- Same eyes, nose, lips, jawline, skin tone, skin texture, expression
- Same apparent age, same ethnicity presentation
- Do NOT beautify, smooth, slim, or modify ANY facial feature

#### 2. HAIR — UNCHANGED
- Same color, length, texture, style, parting as the input photo
- Do NOT restyle, recolor, or modify hair in any way

#### 3. BODY — UNCHANGED
- Same body frame, proportions, pose, posture
- The new clothing must FIT this person's actual body shape
- Do NOT slim, bulk up, or idealize the body

#### 4. BACKGROUND & ENVIRONMENT — UNCHANGED
- Keep the original photo's background, lighting direction, and atmosphere
- The new clothing should look naturally lit by the existing scene lighting

#### 5. POSE — UNCHANGED
- Keep the exact same body position, arm placement, leg stance
- Clothing should drape naturally over the existing pose

## CRITICAL PROHIBITIONS

1. Do NOT regenerate the person — EDIT the existing photo
2. Do NOT change face shape, skin color, or any facial feature
3. Do NOT smooth skin or apply beauty filters
4. Do NOT change the background or environment
5. Do NOT change body proportions or pose
6. Do NOT make it look illustrated, painted, or AI-generated — maintain
   the photographic quality of the original
7. The result should look like the person actually changed clothes and took
   another photo in the same spot

## QUALITY REQUIREMENTS

- The new clothing must have natural fabric behavior (drape, fold, wrinkle)
- Clothing must fit naturally on the person's actual body shape
- Lighting on clothing must match the scene's existing light direction
- Edges between skin and clothing must be clean and natural
- The overall image should look like a real photograph, not a composite
"""

    def render_style_transfer(
        self,
        identity_features: str,
        style_directive: str,
        composition_settings: str,
    ) -> str:
        """
        渲染 Step 2 风格换装生成 Prompt。

        Args:
            identity_features: Step 0 输出的身份特征文本
            style_directive: Step 3 输出的结构化风格指令
            composition_settings: 构图参数块

        Returns:
            可直接传给 OpenAI 图像生成 API 的完整 Prompt
        """
        return self.STYLE_TRANSFER_TEMPLATE.format(
            identity_features=identity_features.strip(),
            style_directive=style_directive.strip(),
            composition_settings=composition_settings.strip(),
        )

    # ============================================================
    # Retry Prompts (Failure Recovery)
    # ============================================================

    RETRY_FACE_MISMATCH: str = (
        "OVERRIDE PRIORITY: The identity of the person is MORE IMPORTANT than the "
        "clothing style. If achieving perfect style requires changing the face, "
        "SACRIFICE STYLE ACCURACY and preserve the face. A recognizable person "
        "in slightly off-style clothing is better than a perfect outfit on a "
        "stranger's face."
    )

    RETRY_FABRIC_PHYSICS: str = (
        "FABRIC PHYSICS REQUIREMENT: Show natural gravity, tension, and compression. "
        "The coat should hang and fold under its own weight. The jeans should show "
        "slight bunching at the ankle. The sweater should have natural bulk and "
        "softness. Clothes must interact with the body beneath them."
    )

    RETRY_ANTI_BEAUTY: str = (
        "ANTI-BEAUTIFICATION LOCK: Output must match the reference person's EXACT "
        "level of attractiveness, skin quality, and facial symmetry. Do NOT improve "
        "complexion. Do NOT slim face. Do NOT enlarge eyes. Do NOT enhance features. "
        "This is a documentary-accurate representation, not a dating app photo."
    )

    RETRY_ATMOSPHERE: str = (
        "ATMOSPHERE LOCK: The overall color temperature, contrast, and environmental "
        "mood must match the specified era/region reference. Do NOT default to "
        "generic bright studio lighting if the style calls for moody evening ambiance."
    )

    # ============================================================
    # Utility: Identity parser
    # ============================================================

    @staticmethod
    def parse_identity_text(text: str) -> dict[str, str]:
        """
        将 Step 0 的文本输出解析为结构化字典。

        Args:
            text: GPT-4o Vision 返回的身份特征文本

        Returns:
            dict, key 为大写字段名, value 为对应值
        """
        result: dict[str, str] = {}
        in_profile = False
        for line in text.splitlines():
            line = line.strip()
            if line == "---IDENTITY PROFILE BEGIN---":
                in_profile = True
                continue
            if line == "---IDENTITY PROFILE END---":
                break
            if not in_profile or not line:
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    @staticmethod
    def parse_styling_brief(text: str) -> dict[str, str]:
        """
        将 Step 3 的风格指令解析为结构化字典。

        Args:
            text: GPT-4o Text 返回的风格指令文本

        Returns:
            dict, key 为字段名, value 为对应值
        """
        result: dict[str, str] = {}
        in_brief = False
        current_key: str | None = None
        current_value: list[str] = []

        for line in text.splitlines():
            line = line.strip()
            if line == "---STYLING BRIEF---":
                in_brief = True
                continue
            if line == "---END STYLING BRIEF---":
                break
            if not in_brief:
                continue

            # Detect new key (format: "Key: value" or "Key:")
            if line and ":" in line and not line.startswith("-"):
                # Save previous key-value pair
                if current_key and current_value:
                    result[current_key] = "\n".join(current_value).strip()
                # Start new key
                key_part, val_part = line.split(":", 1)
                current_key = key_part.strip()
                current_value = [val_part.strip()] if val_part.strip() else []
            elif current_key:
                current_value.append(line)

        # Save last pair
        if current_key and current_value:
            result[current_key] = "\n".join(current_value).strip()

        return result


# ============================================================
# Quick Test / Usage Example
# ============================================================

if __name__ == "__main__":
    engine = PromptEngine()

    # Example 1: Step 0
    print("=" * 60)
    print("STEP 0: IDENTITY EXTRACTION PROMPT")
    print("=" * 60)
    print(engine.extract_identity()[:500] + "...\n")

    # Example 2: Step 1
    identity_sample = (
        "GENDER: Male\n"
        "AGE_RANGE: mid 20s\n"
        "FACE_SHAPE: oval\n"
        "OVERALL_SIGNATURE: A young East Asian male with sharp jawline..."
    )
    print("=" * 60)
    print("STEP 1: STANDARD PORTRAIT PROMPT (preview)")
    print("=" * 60)
    std_prompt = engine.render_standard_portrait(identity_sample)
    print(std_prompt[:500] + "...\n")

    # Example 3: Step 3
    print("=" * 60)
    print("STEP 3: STYLE PARSER PROMPT (preview)")
    print("=" * 60)
    parser_prompt = engine.parse_style(
        raw_text="复古港风，像老电影里的感觉",
        tags=["vintage", "autumn", "daily", "oversized"],
        gender_hint="male",
        season_hint="autumn",
        occasion_hint="daily",
    )
    print(parser_prompt[:500] + "...\n")

    # Example 4: Step 2
    style_directive_sample = (
        "---STYLING BRIEF---\n"
        "Style Name: 90s Hong Kong Cinema\n"
        "Overall Mood: Nostalgic urban romance\n"
        "Top Garment: Oversized camel wool overcoat...\n"
        "---END STYLING BRIEF---"
    )
    composition_sample = (
        "---COMPOSITION PARAMETERS---\n"
        "Aspect Ratio: 3:4 vertical\n"
        "Framing: Full body\n"
        "---END COMPOSITION PARAMETERS---"
    )
    print("=" * 60)
    print("STEP 2: STYLE TRANSFER PROMPT (preview)")
    print("=" * 60)
    final_prompt = engine.render_style_transfer(
        identity_features=identity_sample,
        style_directive=style_directive_sample,
        composition_settings=composition_sample,
    )
    print(final_prompt[:500] + "...\n")
