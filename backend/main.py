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
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
