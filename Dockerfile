# MistakeCoach 单服务部署：FastAPI 同时托管前端构建产物
# Hugging Face Spaces（sdk: docker, app_port: 7860）与其他 Docker 平台通用

# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：后端运行时 ----
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# 前端构建产物拷到 main.py 约定的静态托管位置（../frontend/dist）
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
