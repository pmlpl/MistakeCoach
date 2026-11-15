"""Supabase 访问层（云端同步）：JWT 验签走 JWKS 公钥端点（不存任何 JWT 密钥），
数据读写走 PostgREST + Secret Key（服务端专用，绕过 RLS——因此每个查询都显式按 user_id 过滤）。

未配置 SUPABASE_URL / SUPABASE_SECRET_KEY 时 enabled() 为 False，
应用退化为纯本地模式（游客功能完全不受影响）。
"""
import os

import httpx
import jwt
from jwt import PyJWKClient

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SECRET_KEY = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()

_jwks_client: PyJWKClient | None = None


def enabled() -> bool:
    """云端同步是否已配置（部署时给 Render 配两个环境变量即可开启）"""
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)


def verify_token(authorization: str | None) -> dict | None:
    """验证 Authorization: Bearer <jwt>（前端 supabase-js 登录后的 access token）。

    RS256 验签公钥从 Supabase JWKS 端点动态获取并缓存；通过返回 payload（sub = 用户 id），
    无效/过期/未登录返回 None。"""
    global _jwks_client
    if not enabled() or not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True)
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"require": ["exp", "sub"]},
        )
        return payload
    except Exception:
        return None


def rest(path: str, *, method: str = "GET", params: dict | None = None,
         json_body=None, prefer: str | None = None) -> httpx.Response:
    """PostgREST 一次调用。path 为表名（如 "cards"），params 为 PostgREST 查询参数。"""
    headers = {
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "apikey": SUPABASE_SECRET_KEY,  # 新 key 体系下可省，带上兼容旧行为
    }
    if prefer:
        headers["Prefer"] = prefer
    return httpx.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{path}",
        params=params,
        json=json_body,
        headers=headers,
        timeout=15,
    )
