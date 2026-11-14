"""OpenAI 兼容供应商预设与调用配置解析（BYOK：模型与 Key 全部来自访客请求，服务端不内置任何 Key）

主流模型服务都提供 OpenAI 兼容接口（Claude 走 Anthropic 官方 OpenAI 兼容层、
Gemini 走官方 OpenAI 兼容端点），后端只需实现一条 /chat/completions 通道。
识别（vision）与对话（chat）各自独立配置，互不影响。
"""
import os

from fastapi import HTTPException, Request

# 供应商预设：base 为 OpenAI 兼容基底（后端拼 /chat/completions）
# vision/chat 为该家默认模型名；env_* 为服务端默认值覆盖（请求未显式指定模型时生效）
PROVIDERS = {
    "zhipu": {
        "label": "智谱 GLM",
        "base": "https://open.bigmodel.cn/api/paas/v4",
        "vision_model": "glm-4v-flash",
        "chat_model": "glm-4.7-flash",
        "env_vision": "ZHIPU_MODEL",
        "env_chat": "ZHIPU_CHAT_MODEL",
        "legacy_key_header": "X-Zhipu-Key",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base": "https://api.deepseek.com",
        "vision_model": "deepseek-flash",
        "chat_model": "deepseek-chat",
        "env_vision": "DEEPSEEK_VISION_MODEL",
        "env_chat": "DEEPSEEK_MODEL",
        "legacy_key_header": "X-Deepseek-Key",
    },
    "openai": {
        "label": "OpenAI",
        "base": "https://api.openai.com/v1",
        "vision_model": "gpt-4o-mini",
        "chat_model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Claude",
        "base": "https://api.anthropic.com/v1",
        "vision_model": "claude-sonnet-4-5",
        "chat_model": "claude-sonnet-4-5",
    },
    "gemini": {
        "label": "Gemini",
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "vision_model": "gemini-2.5-flash",
        "chat_model": "gemini-2.5-flash",
    },
    "custom": {
        "label": "自定义",
        "base": "",
        "vision_model": "",
        "chat_model": "",
    },
}


def resolve_config(
    request: Request,
    *,
    kind: str,
    header_prefix: str,
    default_provider: str,
    provider: str = "",
    model: str = "",
    base_url: str = "",
) -> dict:
    """解析一次模型调用的 {url, model, key, label}。

    kind: "vision"（识别）| "chat"（对话/笔记）
    header_prefix: 请求头前缀（"X-Recognize" / "X-Chat"）
    provider/model/base_url: 请求体显式配置（对话走 body；识别可走同前缀头）
    Key 优先级：X-<prefix>-Key > 该供应商旧头（X-Zhipu-Key / X-Deepseek-Key）
    """
    p = (
        (provider or "").strip()
        or (request.headers.get(f"{header_prefix}-Provider") or "").strip()
        or default_provider
    ).strip()
    preset = PROVIDERS.get(p)
    if preset is None:
        raise HTTPException(status_code=400, detail=f"不支持的模型供应商「{p}」，请到设置页重新选择")

    model = (model or "").strip() or (request.headers.get(f"{header_prefix}-Model") or "").strip()
    if not model:
        env_name = preset.get("env_vision") if kind == "vision" else preset.get("env_chat")
        model = (os.getenv(env_name, "") if env_name else "").strip()
    if not model:
        model = preset["vision_model"] if kind == "vision" else preset["chat_model"]
    if not model:
        raise HTTPException(status_code=400, detail="自定义模型需要填写模型名，请到设置页补全")

    base = (
        (base_url or "").strip()
        or (request.headers.get(f"{header_prefix}-Base") or "").strip()
        or preset["base"]
    ).strip()
    if not base:
        raise HTTPException(status_code=400, detail="自定义模型需要填写接口地址（OpenAI 兼容 Base URL），请到设置页补全")

    key = (request.headers.get(f"{header_prefix}-Key") or "").strip()
    if not key:
        legacy = preset.get("legacy_key_header")
        if legacy:
            key = (request.headers.get(legacy) or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"还没有配置 {preset['label']} 的 Key：请到设置页填写后重试（Key 仅存本机，不会上传服务器存储）",
        )

    return {
        "url": base.rstrip("/") + "/chat/completions",
        "model": model,
        "key": key,
        "label": preset["label"],
    }
