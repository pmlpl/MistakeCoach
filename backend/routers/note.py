"""/api/note：对话 transcript -> 访客选择的对话模型按固定 Schema 生成错题卡 JSON（6.3；容错：失败重试一次）"""
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from jsonfix import extract_json
from providers import resolve_config

router = APIRouter(prefix="/api", tags=["note"])

CATEGORIES = ("概念不清", "计算失误", "审题偏差", "方法缺失")


class NoteMessage(BaseModel):
    role: str
    content: str


class NoteChatModel(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""


class NoteRequest(BaseModel):
    question_text: str
    student_work: str = ""
    transcript: list[NoteMessage] = []
    chat_provider: str = ""  # 兼容旧前端：deepseek | zhipu
    chat: NoteChatModel | None = None


_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "note.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _normalize(card: dict) -> dict:
    """字段兜底与归一：category 枚举外的归"方法缺失"（6.3），其余补默认值保证前端渲染稳定"""
    if not isinstance(card, dict):
        raise ValueError("模型输出不是 JSON 对象")
    if not (card.get("question") or "").strip():
        raise ValueError("缺少题目内容")
    if not (card.get("correct_solution") or []):
        raise ValueError("缺少解题步骤")

    reason = card.get("wrong_reason") or {}
    category = (reason.get("category") or "").strip()
    card["wrong_reason"] = {
        "category": category if category in CATEGORIES else "方法缺失",
        "analysis": (reason.get("analysis") or "").strip(),
    }
    card["subject"] = (card.get("subject") or "其他").strip() or "其他"
    card["grade_band"] = (card.get("grade_band") or "初中").strip() or "初中"
    kp = card.get("knowledge_points")
    card["knowledge_points"] = [str(k).strip() for k in kp if str(k).strip()][:3] if isinstance(kp, list) else []
    card["correct_solution"] = [str(s).strip() for s in card["correct_solution"] if str(s).strip()]
    for k in ("student_wrong_answer", "final_answer", "variant_question", "variant_answer", "insight_quote", "chat_summary"):
        card[k] = str(card.get(k) or "").strip()
    return card


@router.post("/note")
async def note(req: NoteRequest, request: Request):
    # 纯 BYOK（3.6）：服务端不内置任何 Key；模型与 Key 全部来自访客请求
    chat_cfg = req.chat if (req.chat and (req.chat.provider or req.chat.model or req.chat.base_url)) else None
    cfg = resolve_config(
        request,
        kind="chat",
        header_prefix="X-Chat",
        default_provider="deepseek",
        provider=chat_cfg.provider if chat_cfg else (req.chat_provider or ""),
        model=chat_cfg.model if chat_cfg else "",
        base_url=chat_cfg.base_url if chat_cfg else "",
    )
    api_key, model = cfg["key"], cfg["model"]

    transcript_text = "\n".join(
        f"{'学生' if m.role == 'user' else '教练'}：{m.content}"
        for m in req.transcript
        if m.role in ("user", "assistant") and m.content
    )
    # 占位符用 replace 而非 format：prompt 里有 JSON 花括号，format 会误解析
    system_prompt = _load_prompt().replace("{question_text}", req.question_text).replace("{student_work}", req.student_work)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"【对话记录】\n{transcript_text or '（无对话内容）'}"},
    ]

    async def call_once() -> dict:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            resp = await client.post(
                cfg["url"],
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "stream": False},
            )
        if resp.status_code in (401, 403):
            raise HTTPException(status_code=502, detail=f"{cfg['label']} Key 无效或已过期，请在设置页检查后重试")
        if resp.status_code == 429:
            raise HTTPException(status_code=502, detail="模型当前访问量过大，请稍后再试，或到设置页切换对话模型")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"对话服务返回异常（{resp.status_code}），请稍后再试")
        content = resp.json()["choices"][0]["message"]["content"]
        return _normalize(extract_json(content))

    # Schema 校验失败重试一次（6.3）
    try:
        card = await call_once()
    except HTTPException:
        raise
    except Exception:
        try:
            card = await call_once()
        except Exception:
            raise HTTPException(status_code=502, detail="没能生成错题卡，建议回对话页再聊几轮后重试")

    card["id"] = str(uuid.uuid4())
    card["created_at"] = datetime.now(timezone.utc).isoformat()
    return json.loads(json.dumps(card, ensure_ascii=False))
