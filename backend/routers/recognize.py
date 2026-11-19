"""/api/recognize：multipart 图片 -> 访客选择的视觉模型 -> 结构化 JSON（BYOK，失败重试一次）"""
import base64
import json
import os

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from jsonfix import extract_json
from providers import resolve_config

router = APIRouter(prefix="/api", tags=["recognize"])

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "recognize.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _normalize_text(s: str) -> str:
    """换行归一：模型有时输出真实 \n，有时双转义成字面 \\n，统一收敛为真实换行"""
    return s.replace("\\n", "\n").strip()


async def _call_vision(image_bytes: bytes, cfg: dict) -> dict:
    """OpenAI 兼容视觉调用——必须 async（同步 httpx 在 FastAPI 里会卡死事件循环）"""
    b64 = base64.b64encode(image_bytes).decode()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        resp = await client.post(
            cfg["url"],
            headers={"Authorization": f"Bearer {cfg['key']}"},
            json={
                "model": cfg["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            {"type": "text", "text": _load_prompt()},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return extract_json(content)


@router.post("/recognize")
async def recognize(request: Request, image: UploadFile = File(...)):
    import logging
    _log = logging.getLogger("recognize")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片为空，请重新选择")

    # BYOK：识别模型与 Key 全部来自访客请求头（未配置时默认智谱 GLM-4V-Flash）
    try:
        cfg = resolve_config(request, kind="vision", header_prefix="X-Recognize", default_provider="zhipu")
    except HTTPException:
        raise

    try:
        result = await _call_vision(image_bytes, cfg)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        _log.warning("recognize HTTP %s from %s", code, cfg["label"])
        if code in (401, 403):
            raise HTTPException(status_code=502, detail=f"{cfg['label']} Key 无效或已过期，请在设置页检查后重试")
        if code == 429:
            raise HTTPException(status_code=502, detail="模型当前访问量过大，请稍后再试，或到设置页切换识别模型")
        raise HTTPException(status_code=502, detail=f"识别服务返回异常（{code}），请稍后再试")
    except httpx.HTTPError as e:
        _log.warning("recognize network error from %s: %s", cfg["label"], e)
        raise HTTPException(status_code=502, detail="识别服务暂时不可用，请稍后再试")
    except KeyError as e:
        _log.warning("recognize malformed response from %s: missing key %s", cfg["label"], e)
        raise HTTPException(status_code=502, detail="识别服务返回异常，请稍后再试")
    except (json.JSONDecodeError, ValueError):
        # 模型返回非 JSON，重试一次
        _log.info("recognize parse error from %s, retrying", cfg["label"])
        try:
            result = await _call_vision(image_bytes, cfg)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="AI 没能正确识别这张图片，建议换个角度、光线充足时重新拍一张",
            )

    # 兜底补全字段，保证前端拿到的结构稳定
    return {
        "subject": result.get("subject") or "其他",
        "question_text": _normalize_text(result.get("question_text") or ""),
        "student_work": _normalize_text(result.get("student_work") or ""),
        "has_handwriting": bool(result.get("has_handwriting")),
    }
