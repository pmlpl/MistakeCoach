"""/api/chat：SSE 对话 —— 固定基底 prompt + 末尾状态指令，流式转调 DeepSeek（文档 6.2 / 7.5）"""
import json
import os
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["chat"])

# 对话供应商映射（3.6 BYOK：服务端不内置任何 Key，Key 全部来自请求头）
PROVIDERS = {
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "env_model": "DEEPSEEK_MODEL",
        "key_header": "X-Deepseek-Key",
        "label": "DeepSeek",
    },
    "zhipu": {
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "default_model": "glm-4-flash",
        "env_model": "ZHIPU_CHAT_MODEL",
        "key_header": "X-Zhipu-Key",
        "label": "智谱 GLM",
    },
}

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "chat.txt")

# 回复末尾的机器标记（7.5）：⟦PHASE:P3|HINT:L2|MODE:guide⟧，HINT/MODE 可缺省（缺省沿用原状态）
_MARKER_RE = re.compile(r"⟦PHASE:(P[1-4])(?:\|HINT:L([0-4]))?(?:\|MODE:(guide|direct))?⟧")

PHASES = ("P1", "P2", "P3", "P4")
MODES = ("guide", "direct")


class ChatState(BaseModel):
    phase: str = "P1"
    hint_level: int = 0
    mode: str = "guide"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question_text: str = ""
    student_work: str = ""
    state: ChatState = ChatState()
    messages: list[ChatMessage] = []
    chat_provider: str = "deepseek"  # deepseek | zhipu（3.6 访客在设置页选择）


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _relay(up: httpx.Response, client: httpx.AsyncClient, state: ChatState):
    """把 DeepSeek 的 OpenAI 风格流式响应转成前端 SSE（6.2）：
    增量发 {"delta": ...}；流完后解析回复末尾标记发 {"state": ...}，再发 [DONE]。
    剥离标记方案：发增量时从最后一个 ⟦ 起扣住暂存不下发，保证标记字符不漏进正文。"""

    async def gen():
        try:
            raw = []  # 原始完整回复（含标记）
            pending = ""  # 从最后一个 ⟦ 起扣住、暂不下发的尾巴
            async for line in up.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                piece = (choices[0].get("delta") or {}).get("content") if choices else ""
                if not piece:
                    continue
                raw.append(piece)
                pending += piece
                idx = pending.rfind("⟦")
                if idx == -1:
                    yield _sse({"delta": pending})
                    pending = ""
                elif idx > 0:
                    yield _sse({"delta": pending[:idx]})
                    pending = pending[idx:]

            text = "".join(raw)
            if not text.strip():
                # DeepSeek 偶发返回空流（HTTP 200 但零内容）：显式报错，前端不再出现静默空气泡
                yield _sse({"error": "AI 返回了空回复，请重试一次"})
                yield "data: [DONE]\n\n"
                return
            marker = None
            for marker in _MARKER_RE.finditer(text):
                pass  # 取最后一个标记
            if marker:
                rest = text[marker.end():].strip()
                # 罕见情况：模型把正文写在标记之后，补发保证不丢字
                if rest and "⟦" not in rest and "⟧" not in rest:
                    yield _sse({"delta": rest})

            # 新状态：解析标记得到；标记缺失或字段缺省时沿用入参
            new_state = {
                "phase": state.phase if state.phase in PHASES else "P1",
                "hint_level": max(0, min(4, state.hint_level)),
                "mode": state.mode if state.mode in MODES else "guide",
            }
            if marker:
                new_state["phase"] = marker.group(1)
                if marker.group(2) is not None:
                    new_state["hint_level"] = int(marker.group(2))
                if marker.group(3) is not None:
                    new_state["mode"] = marker.group(3)
            yield _sse({"state": new_state})
            yield "data: [DONE]\n\n"
        finally:
            await up.aclose()
            await client.aclose()

    return gen()


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    # 纯 BYOK（3.6）：服务端不内置任何 Key，Key 只来自访客请求头
    provider = PROVIDERS.get((req.chat_provider or "deepseek").strip()) or PROVIDERS["deepseek"]
    api_key = (request.headers.get(provider["key_header"], "") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail=f"还没有你的 {provider['label']} Key：请在应用「设置页」填写后重试（Key 仅存本机，不会上传服务器存储）")
    model = (os.getenv(provider["env_model"], "") or "").strip() or provider["default_model"]

    # 固定基底 system prompt：变量填充（replace 而非 format，防 prompt 中 JSON 花括号误解析），不随阶段切换（7.5）
    system_prompt = _load_prompt().replace("{question_text}", req.question_text).replace("{student_work}", req.student_work)
    # 状态走末尾（7.5）：追加到最后一条消息内容内——供应商兼容（智谱要求消息严格交替，
    # 独立 system 指令会 1214 报错），且不影响 DeepSeek 前缀缓存（追加处即最新消息）
    messages = [{"role": "system", "content": system_prompt}]
    messages += [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant") and m.content
    ]
    # 保险：合并连续同角色消息（对 DeepSeek 是无害的幂等操作）
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(dict(m))
    messages = merged

    state_directive_text = (
        f"\n\n【当前状态指令】phase={req.state.phase}，hint_level=L{req.state.hint_level}，mode={req.state.mode}。"
        "按 system prompt 中该阶段、该梯度、该模式的规则回复，并在回复末尾输出状态标记。"
    )
    if messages and messages[-1]["role"] != "system":
        messages[-1]["content"] += state_directive_text
    else:
        messages.append({"role": "user", "content": state_directive_text.strip()})

    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    up_req = client.build_request(
        "POST",
        provider["url"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "stream": True},
    )
    try:
        up = await client.send(up_req, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(status_code=502, detail="对话服务暂时不可用，请稍后再试")
    if up.status_code != 200:
        await up.aclose()
        await client.aclose()
        if up.status_code in (401, 403):
            raise HTTPException(status_code=502, detail=f"{provider['label']} Key 无效或已过期，请在设置页检查后重试")
        raise HTTPException(status_code=502, detail=f"对话服务返回异常（{up.status_code}），请稍后再试")

    return StreamingResponse(
        _relay(up, client, req.state),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
