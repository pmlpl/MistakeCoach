"""/api/cards：登录用户的错题卡云端同步（一个接口 = 上传 upsert + 下载全量）。

同步语义（合并，非镜像）：本地全部卡 upsert 上去，云端全部卡返回下来；
前端只把"云端有而本地没有"的合并进本地。**本地删除不传播**——
两台设备场景下镜像语义会误删未同步过的卡，合并语义最安全（面试可聊的边界取舍）。
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from supabase import enabled, rest, verify_token

router = APIRouter(prefix="/api", tags=["cards"])


def require_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI 依赖：校验 Bearer JWT，返回 Supabase 用户 id；未登录/无效 → 401"""
    payload = verify_token(authorization)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="登录状态已过期，请到设置页退出后重新登录再同步")
    return payload["sub"]


class SyncIn(BaseModel):
    cards: list[dict]  # 本地错题卡全量（mc_cards 原样）


def _row(card: dict, user_id: str) -> dict | None:
    """卡对象 → 表行：card_id 必有（前端生成），subject/category 提取做冗余索引"""
    card_id = card.get("id")
    if not card_id:
        return None
    return {
        "user_id": user_id,
        "card_id": str(card_id),
        "card": card,
        "subject": card.get("subject") or "",
        "category": (card.get("wrong_reason") or {}).get("category") or "",
    }


@router.post("/cards/sync")
def sync_cards(body: SyncIn, user_id: str = Depends(require_user)):
    if not enabled():
        raise HTTPException(status_code=503, detail="云端同步未启用（服务端未配置 Supabase）")

    rows = [r for c in body.cards if isinstance(c, dict) and (r := _row(c, user_id))]
    if rows:
        up = rest(
            "cards",
            method="POST",
            json_body=rows,
            # 复合主键 (user_id, card_id) 冲突时更新：重复同步不产生重复行
            prefer="resolution=merge-duplicates,return=minimal",
        )
        if up.status_code >= 300:
            raise HTTPException(status_code=502, detail="云端上传失败，请稍后再试")

    down = rest(
        "cards",
        params={"select": "card", "user_id": f"eq.{user_id}", "order": "updated_at.desc"},
    )
    if down.status_code >= 300:
        raise HTTPException(status_code=502, detail="云端读取失败，请稍后再试")
    return {"cards": [row["card"] for row in down.json()]}
