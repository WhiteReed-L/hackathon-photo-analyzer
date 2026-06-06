"""POST /api/chat — Dialogue model that classifies user intent and responds."""
import json

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI

import config
from models import ChatRequest, ChatResponse
from routes.user import require_user

router = APIRouter()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_CHAT_API_KEY,
            base_url=config.OPENAI_CHAT_BASE_URL,
        )
    return _client


_SYSTEM_PROMPT = """\
你是"小费"，一位专业时尚搭配助手。你的任务是和用户对话，判断用户意图，并在需要生成图片时提供详细的穿搭描述。

## 你会收到的上下文信息

- 用户当前选择的服装类型标签（clothing_tags）
- 用户当前选择的风格标签（style_tags）
- 用户当前选择的场景标签（scene_tags）
- 用户使用的功能路径（path）

## 判断规则

1. **穿搭需求**（想换衣服、换颜色、换风格、想要某种搭配、描述穿搭偏好等）：
   - action = "generate"
   - text = 简短确认（如"好的，帮你换成蓝色系的搭配"）
   - prompt = 详细的英文穿搭描述 prompt（见下方格式要求）

2. **闲聊/提问/咨询建议**（如"什么颜色适合我"、"你好"、"谢谢"等）：
   - action = "reply"
   - text = 正常中文回复
   - prompt = null

## prompt 字段格式要求（仅 action="generate" 时输出）

综合用户的文字描述和选择的标签，生成一段英文穿搭描述，要求：
- 明确描述服装类型、风格、颜色、材质、剪裁
- 融合用户选择的标签信息（服装类型、风格、场景）
- 适配场景需求（如通勤要正式、约会要精致、运动要舒适）
- 具体且可视化，避免模糊描述
- 示例：\"A smart-casual outfit: navy blue slim-fit chinos, white linen button-down shirt with rolled sleeves, tan leather loafers, minimalist silver watch. Color palette: navy, white, tan. Suitable for a weekend brunch date.\"

## 输出格式

只输出 JSON，不要输出其他内容：
{"action": "reply"或"generate", "text": "你的中文回复", "prompt": "英文穿搭描述或null"}\
"""


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user_id: int = Depends(require_user),
):
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

    # Build context block from tags
    context_parts = []
    if body.path:
        context_parts.append(f"功能路径: {body.path}")
    if body.clothing_tags:
        context_parts.append(f"用户选择的服装类型: {', '.join(body.clothing_tags)}")
    if body.style_tags:
        context_parts.append(f"用户选择的风格: {', '.join(body.style_tags)}")
    if body.scene_tags:
        context_parts.append(f"用户选择的场景: {', '.join(body.scene_tags)}")

    if context_parts:
        messages.append({
            "role": "system",
            "content": "当前用户选择的标签信息：\n" + "\n".join(context_parts),
        })

    if body.history:
        for h in body.history[-6:]:
            role = h.get("role", "user")
            text = h.get("text", "")
            if text and role in ("user", "assistant"):
                messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": body.text})

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=config.OPENAI_CHAT_MODEL,
            messages=messages,
            max_completion_tokens=512,
            temperature=0.3,
        )
        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        action = result.get("action", "reply")
        text = result.get("text", "")
        prompt = result.get("prompt") or None

        if action not in ("reply", "generate"):
            action = "reply"

        return ChatResponse(action=action, text=text, prompt=prompt)
    except json.JSONDecodeError:
        return ChatResponse(action="reply", text=raw if raw else "抱歉，我没有理解你的意思，能再说一次吗？")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"对话模型调用失败: {str(e)}")
