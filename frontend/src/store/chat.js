/** 对话状态机（7.5 硬状态机）：前端硬规则 + 后端末尾标记覆盖；notice 为纯 UI 系统气泡 */
import { reactive } from 'vue'
import { session } from './session'

let seq = 0
let stuck = 0 // 连续"不知道/不会"计数（硬规则：连续 2 轮 hint_level+1）

export const chat = reactive({
  messages: [], // {id, role: 'user'|'assistant'|'notice', content}
  state: { phase: 'P1', hint_level: 0, mode: 'guide' },
  sending: false,
})

const STUCK_RE = /(不知道|不会|没思路|不清楚|不晓得|想不出|看不懂)/
const DIRECT_RE = /(直接讲|直接给|给我答案|告诉我答案|不会了|说答案)/

const DRAFT_KEY = 'mc_chat_draft' // 存 { v: 2, buckets: { [sessionId]: 会话桶 } }
const LAST_SID_KEY = 'mc_chat_last_sid' // 最近活跃会话 id：刷新后无 sid 进入时恢复它
const MAX_BUCKETS = 10 // 防长用撑爆 localStorage：只保留最近 10 个未完成会话桶

/** 每道题一个会话桶 id：拍题识别成功时分配（Shoot.vue），拍新题绝不触碰其他桶 */
export function newSessionId() {
  return 's_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

/** 读全部分桶；兼容旧版单份草稿——读到旧结构时一次性迁移为 legacy 桶并回写，老用户未完成对话不丢 */
function readBuckets() {
  try {
    const raw = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')
    if (!raw) return {}
    if (raw.v === 2 && raw.buckets && typeof raw.buckets === 'object') return raw.buckets
    if (raw.question && Array.isArray(raw.messages)) {
      const buckets = { legacy: raw }
      writeBuckets(buckets)
      localStorage.setItem(LAST_SID_KEY, 'legacy')
      return buckets
    }
    return {}
  } catch {
    return {}
  }
}

function writeBuckets(buckets) {
  localStorage.setItem(DRAFT_KEY, JSON.stringify({ v: 2, buckets }))
}

/** 草稿续聊（FR-12）：当前对话存入 session.sessionId 对应的桶；notice 气泡不入档 */
export function saveDraft() {
  const sid = session.sessionId
  const messages = chat.messages.filter((m) => (m.role === 'user' || m.role === 'assistant') && m.content)
  if (!sid || !messages.length) return
  const buckets = readBuckets()
  buckets[sid] = {
    question: {
      subject: session.subject,
      gradeBand: session.gradeBand,
      questionText: session.questionText,
      studentWork: session.studentWork,
      hasHandwriting: session.hasHandwriting,
    },
    messages,
    state: { ...chat.state },
    updatedAt: Date.now(), // 多桶并存时「继续上次对话」取最近更新的桶
  }
  // 超限裁剪最旧的桶（当前桶 updatedAt 最新，不会被裁掉）
  const keys = Object.keys(buckets)
  if (keys.length > MAX_BUCKETS) {
    keys.sort((a, b) => (buckets[a].updatedAt || 0) - (buckets[b].updatedAt || 0))
    keys.slice(0, keys.length - MAX_BUCKETS).forEach((k) => delete buckets[k])
  }
  writeBuckets(buckets)
  localStorage.setItem(LAST_SID_KEY, sid)
}

/** 读取指定会话桶；不传 sid 读最近活跃桶（刷新续聊）。返回值带 sid 便于回绑 session */
export function loadDraft(sid) {
  const key = sid || localStorage.getItem(LAST_SID_KEY)
  if (!key) return null
  const buckets = readBuckets()
  return buckets[key] ? { ...buckets[key], sid: key } : null
}

/** 最近一个未完成会话桶（多个时取最近更新的）：「继续上次对话」横幅指向它 */
export function latestDraft() {
  const buckets = readBuckets()
  let best = ''
  for (const key of Object.keys(buckets)) {
    if (!best || (buckets[key].updatedAt || 0) > (buckets[best].updatedAt || 0)) best = key
  }
  return best ? { ...buckets[best], sid: best } : null
}

/** 清空指定会话桶（生成错题卡成功后只清当前桶）；不传 sid 清最近活跃桶 */
export function clearDraft(sid) {
  const key = sid || localStorage.getItem(LAST_SID_KEY)
  if (!key) return
  const buckets = readBuckets()
  if (buckets[key]) {
    delete buckets[key]
    writeBuckets(buckets)
  }
  if (localStorage.getItem(LAST_SID_KEY) === key) localStorage.removeItem(LAST_SID_KEY)
}

export function pushMessage(role, content) {
  const id = ++seq
  chat.messages.push({ id, role, content })
  return id
}

export function removeMessage(id) {
  const i = chat.messages.findIndex((m) => m.id === id)
  if (i !== -1) chat.messages.splice(i, 1)
}

export function resetChat() {
  chat.messages.splice(0)
  chat.state = { phase: 'P1', hint_level: 0, mode: 'guide' }
  chat.sending = false
  stuck = 0
}

/** 模式切换：手动与关键词自动切换行为一致（7.5），插入切换说明气泡 */
export function setMode(mode) {
  if (mode === chat.state.mode || !['guide', 'direct'].includes(mode)) return
  chat.state.mode = mode
  stuck = 0
  pushMessage(
    'notice',
    mode === 'direct'
      ? '已切换到讲解模式 —— 我会把错因和步骤直接讲给你听'
      : '已切换回引导模式 —— 我会继续问你，带你自己想通',
  )
  saveDraft()
}

/** 学生消息发送前的硬规则兜底（7.5）：关键词切讲解；连续 2 轮卡壳升提示梯度 */
export function applyHardRules(text) {
  if (DIRECT_RE.test(text)) {
    setMode('direct')
    return
  }
  if (STUCK_RE.test(text)) {
    stuck += 1
    if (stuck >= 2 && chat.state.mode === 'guide' && chat.state.hint_level < 4) {
      chat.state.hint_level += 1
      stuck = 0
    }
  } else {
    stuck = 0
  }
}

/** 后端解析回复末尾标记得到的新状态，覆盖本地 state（非法字段沿用原值） */
export function applyServerState(state) {
  if (!state) return
  chat.state = {
    phase: ['P1', 'P2', 'P3', 'P4'].includes(state.phase) ? state.phase : chat.state.phase,
    hint_level: Number.isFinite(+state.hint_level)
      ? Math.min(4, Math.max(0, +state.hint_level))
      : chat.state.hint_level,
    mode: ['guide', 'direct'].includes(state.mode) ? state.mode : chat.state.mode,
  }
}

/** 发给后端的对话历史：仅真实消息；notice 气泡与空消息不进模型上下文 */
export function apiMessages() {
  return chat.messages
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && m.content)
    .map((m) => ({ role: m.role, content: m.content }))
}
