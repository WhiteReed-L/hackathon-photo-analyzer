"""POST /api/chat — Dialogue model that classifies user intent and responds."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request

import config
from limiter import limiter
from models import ChatRequest, ChatResponse
from routes.user import require_user
from services.ai_client import chat_client

router = APIRouter()

_SYSTEM_PROMPT = """\
你是"小费"，一位专业时尚搭配助手。你的任务是判断用户意图，并在需要生成图片时输出结构化修改指令。
你不是最终图像 prompt 生成器，不要写完整英文生图 prompt。

## 你会收到的上下文信息

- 用户当前选择的服装类型标签（clothing_tags）
- 用户当前选择的风格标签（style_tags）
- 用户当前选择的场景标签（scene_tags）
- 用户使用的功能路径（path）

## 判断规则

1. **穿搭需求**（想换衣服、换颜色、换风格、想要某种搭配、描述穿搭偏好等）：
   - action = "generate"
   - text = 简短确认（如"好的，帮你换成蓝色系的搭配"）
   - intent = "initial_generate" 或 "modify_existing"
   - patch = 用户想改变的结构化字段，只写变化，不要重写整套穿搭
   - constraints.keep = 用户没有要求改变、应该保持的内容
   - constraints.change = 用户明确要求改变的内容
   - prompt = null（仅兼容旧字段，默认不要使用）

2. **闲聊/提问/咨询建议**（如"什么颜色适合我"、"你好"、"谢谢"等）：
   - action = "reply"
   - text = 正常中文回复
   - intent = null
   - patch = null
   - constraints = null
   - prompt = null

## patch 字段格式要求（仅 action="generate" 时输出）

- 用户说"换成蓝色"：patch = {"top_garment": {"color": "蓝色"}} 或根据上下文选择目标单品
- 用户说"鞋子别变"：constraints.keep 包含 "footwear"
- 用户说"整体换成通勤风"：patch = {"overall_style": "通勤", "formality": "商务休闲"}
- 用户说"重新来一套"：intent = "initial_generate"，patch 描述新的整体需求
- 不确定用户要改哪一件时，action = "reply"，text 里追问

## 输出格式

只输出 JSON，不要输出其他内容：
{"action": "reply"或"generate", "text": "你的中文回复", "intent": "initial_generate/modify_existing或null", "patch": {...或null}, "constraints": {"keep": [], "change": []}或null, "prompt": null}\
"""


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(config.CHAT_RATE_LIMIT)
async def chat(
    request: Request,
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
        client = chat_client()
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
        intent = result.get("intent") or None
        patch = result.get("patch") if isinstance(result.get("patch"), dict) else None
        constraints = result.get("constraints") if isinstance(result.get("constraints"), dict) else None
        prompt = result.get("prompt") or None

        if action not in ("reply", "generate"):
            action = "reply"

        return ChatResponse(action=action, text=text, intent=intent, patch=patch, constraints=constraints, prompt=prompt)
    except json.JSONDecodeError:
        return ChatResponse(action="reply", text=raw if raw else "抱歉，我没有理解你的意思，能再说一次吗？")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"对话模型调用失败: {str(e)}")
