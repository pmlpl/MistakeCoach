---
title: MistakeCoach
emoji: 📓
colorFrom: amber
colorTo: yellow
pinned: false
---

# MistakeCoach · 让每道错题都有交代

**在线 demo**：<https://mc.momo.makeup>（Render 免费版，15 分钟无访问会休眠，首次打开约 50 秒）

面向初高中学生的 AI 错题教练 H5：拍下做错的题（连同错误作答）→ AI 苏格拉底式对话还原思路、定位错因 → 自动生成结构化错题卡 → 长图分享、沉淀错题本。

> 教"为什么错"，而不是只教"怎么对"。

## 架构

```mermaid
flowchart TD
    A[拍题页<br/>手机拍照/相册 · 桌面拖拽/点选/粘贴] -->|multipart 图片| B[识别模型<br/>访客自选 · 一次调用 · 结构化识别]
    B --> C[核验页<br/>human-in-the-loop · 人工二次确认]
    C -->|核验后文本| D[对话模型<br/>访客自选 · SSE 流式 · 硬状态机 P1-P4]
    D -->|transcript| E[笔记生成<br/>固定 JSON Schema]
    E --> F[错题卡页<br/>手账荧光卡片 · html2canvas 长图]
    F --> G[错题本<br/>localStorage 免登录 · 牌堆交互]
    G -.登录用户·云同步.-> H[Supabase<br/>PostgreSQL + RLS · JWT 验签]
```

## 核心亮点

1. **多模型分工**：视觉模型只做识别（一次调用），文本模型做对话与笔记生成——成本极低且各取所长。
2. **错因靠对话"钓"**：引导模式不直接给答案，硬状态机（还原思路 → 定位错因 → 提示梯度 L1-L4 → 确认理解）驱动对话；状态走消息末尾保持前缀稳定，命中 LLM 缓存（成本约为未命中的 1/10）。
3. **固定 JSON Schema 契约**：错题卡由 AI 按固定 Schema 输出，前端按 Schema 稳定渲染长图；错因分析强制引用学生原话作为证据。
4. **AI + 人工双兜底**：识别后强制进入核验页（human-in-the-loop）；AI 计算与卷面批改矛盾时会自检并温和指出，不盲从权威答案。
5. **访客自带 Key（BYOK）**：公网演示不烧开发者额度——识别与对话模型均可自选（智谱 GLM·免费 / DeepSeek / OpenAI / Claude / Gemini / 自定义，全部统一走 OpenAI 兼容通道，后端只实现一条调用链）；Key 与模型配置仅存本机 localStorage，随请求使用不落库，**服务端不内置任何 Key**。
6. **账号与云同步**：Supabase 邮箱注册登录，错题卡跨设备同步——合并语义而非镜像（本地删除不传播，防多设备误删）；JWT JWKS 验签（ES256/RS256 兼容）+ RLS 行级安全；不登录游客模式功能完整。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + Vant 4 + vue-router · KaTeX 公式渲染 · html2canvas 长图导出 |
| 后端 | Python FastAPI · SSE 流式转发 · 静态托管前端构建产物 |
| 识别 | 访客自选（默认智谱 GLM-4V-Flash，免费），6 供应商可切 |
| 对话/笔记 | 访客自选（默认 DeepSeek Chat），与识别同一条 OpenAI 兼容通道 |
| 存储 | localStorage（游客模式，存错题卡/对话草稿/访客 Key）；登录用户 Supabase PostgreSQL 云同步 |
| 账号 | Supabase Auth（邮箱注册/登录）· supabase-js 直调 · FastAPI JWKS 验签（ES256/RS256）· RLS 行级安全 |

## 本地运行

```bash
# 1.（可选）覆盖各供应商默认模型名——无需配置任何 Key
cd backend
copy .env.example .env    # 模型名覆盖项可全部留空；SUPABASE_URL/SECRET_KEY 留空 = 纯本地模式

# 2. 启动后端（8001）
pip install -r requirements.txt
python -m uvicorn main:app --port 8001

# 3. 启动前端（5173，已代理 /api 到 8001）
cd ../frontend
npm install
npm run dev
```

> 模型与 Key 在应用「设置页」配置（存浏览器 localStorage，见下方 BYOK 说明）。

## 部署（Render 免费版）

单服务部署：FastAPI 同时托管前端构建产物，见 [Dockerfile](Dockerfile)。

1. 代码推送到 GitHub（本仓库直接 push 即可）
2. [Render](https://render.com) 注册 → **New Web Service** → 连接 GitHub 仓库
3. Runtime 选 **Docker**（自动读取 Dockerfile），Region 选 Singapore（离国内近）
4. Create → 自动构建部署，得到 `https://<名字>.onrender.com` 公网链接

> **无需配置任何模型 Key 环境变量**：本服务不内置 Key（纯 BYOK），访客在应用「设置页」选模型并填自己的 Key——识别与对话均可选智谱 GLM·免费 / DeepSeek / OpenAI / Claude / Gemini / 自定义（OpenAI 兼容接口）。

> **可选——开启账号登录与云同步**：在 Render → Environment 配置 `SUPABASE_URL` 与 `SUPABASE_SECRET_KEY`（Supabase 项目 → Settings → API Keys → Secret keys，仅放服务端）；不配置则为纯本地模式。建表 SQL 见 [backend/supabase_schema.sql](backend/supabase_schema.sql)（在 Supabase SQL Editor 执行一次即可）。

> 免费版 15 分钟无访问会休眠：演示前先自己打开页面预热一次（首次加载约 50 秒）。

## 体验账号

已开启账号登录（错题卡跨设备云同步），可用测试账号体验：

- 邮箱 `admin@qq.com` · 密码 `admin123`

不登录同样可以完整使用（游客模式，数据仅存本机浏览器）。

## 明确不做（后续规划）

- 手机号登录 / 第三方 OAuth（邮箱注册登录已上线）
- 艾宾浩斯复习提醒、学情统计报表
- 错题批量导入、手写 OCR 深度优化
- 错题卡插图、函数图像精细绘制（对话中 SVG 绘图已上线）
