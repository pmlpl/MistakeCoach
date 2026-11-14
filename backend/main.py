"""MistakeCoach 后端入口：FastAPI + CORS + 静态托管"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()  # 读取 backend/.env 中的 API Key

from routers import chat, note, recognize

app = FastAPI(title="MistakeCoach API")

# 开发期放开跨域（Vite 前端 5173 调后端 8000）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recognize.router)
app.include_router(chat.router)
app.include_router(note.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 静态托管前端构建产物（M4 部署时生效：npm run build 后 frontend/dist 出现即自动挂载）
# SPA 回退：history 路由的子路径（/book、/settings、/card/:id）刷新时回 index.html，
# 否则 FastAPI 找不到对应路由会返回 {"detail":"Not Found"}
from fastapi import HTTPException
from fastapi.responses import FileResponse

_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")  # API 路径不回退到页面
        candidate = os.path.normpath(os.path.join(_dist, full_path))
        if full_path and candidate.startswith(os.path.normpath(_dist)) and os.path.isfile(candidate):
            return FileResponse(candidate)  # dist 内的真实文件（如 favicon）按原样返回
        return FileResponse(os.path.join(_dist, "index.html"))
