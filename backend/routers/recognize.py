"""/api/recognize：multipart 图片 -> GLM-4V-Flash -> 结构化 JSON（失败重试一次，502 兜底）"""
import base64
import json
import os

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from jsonfix import extract_json

router = APIRouter(prefix="/api", tags=["recognize"])

GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "recognize.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _normalize_text(s: str) -> str:
    """换行归一：模型有时输出真实 \n，有时双转义成字面 \\n，统一收敛为真实换行"""
    return s.replace("\\n", "\n").strip()


def _call_glm(image_bytes: bytes, user_key: str = "") -> dict:
    # Key 优先级：访客自带（请求头）> 服务端 .env 默认（3.6）
    api_key = (user_key or "").strip() or os.getenv("ZHIPU_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("没有可用的智谱 Key：请在设置页填写，或在 backend/.env 配置后重启服务")

    model = os.getenv("ZHIPU_MODEL", "glm-4v-flash").strip() or "glm-4v-flash"
    b64 = base64.b64encode(image_bytes).decode()
    resp = httpx.post(
        GLM_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
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
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return extract_json(content)


@router.post("/recognize")
async def recognize(request: Request, image: UploadFile = File(...)):
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片为空，请重新选择")

    user_key = request.headers.get("X-Zhipu-Key", "")
    try:
        result = _call_glm(image_bytes, user_key)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except (httpx.HTTPError, KeyError):
        raise HTTPException(status_code=502, detail="识别服务暂时不可用，请稍后再试")
    except (json.JSONDecodeError, ValueError):
        # 模型返回非 JSON，重试一次
        try:
            result = _call_glm(image_bytes, user_key)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
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
