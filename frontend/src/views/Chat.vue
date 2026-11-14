<script setup>
// M2 对话页：SSE 气泡流 + 双模式切换 + KaTeX 渲染（FR-4/5/6；7.5 三触点模式认知）
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { chatStream, noteGenerate } from '../api'
import { renderMixed } from '../utils/render'
import { session } from '../store/session'
import {
  apiMessages,
  applyHardRules,
  applyServerState,
  chat,
  clearDraft,
  loadDraft,
  pushMessage,
  removeMessage,
  resetChat,
  saveDraft,
  setMode,
} from '../store/chat'

const router = useRouter()
const input = ref('')
const listEl = ref(null)
const showRef = ref(false) // 手机端题目参考卡展开开关（桌面端常驻，3.5）
const INTRO_SEEN_KEY = 'mc_intro_seen'

const refQuestionHtml = computed(() => renderMixed(session.questionText))
const refWorkHtml = computed(() => renderMixed(session.studentWork))

// 发送中且当前 AI 气泡还没有内容 → 显示"思考中"
const thinking = computed(() => {
  if (!chat.sending) return false
  const last = chat.messages[chat.messages.length - 1]
  return !last || (last.role === 'assistant' && !last.content)
})

function scrollToBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

/** 请求一轮 AI 回复：流式追加当前 AI 气泡；失败撤掉气泡并 toast 中文报错 */
async function requestReply() {
  chat.sending = true
  const aiId = pushMessage('assistant', '')
  scrollToBottom()
  try {
    await chatStream(
      {
        question_text: session.questionText,
        student_work: session.studentWork,
        state: { phase: chat.state.phase, hint_level: chat.state.hint_level, mode: chat.state.mode },
        messages: apiMessages(),
      },
      (delta) => {
        const m = chat.messages.find((x) => x.id === aiId)
        if (m) m.content += delta
        scrollToBottom()
      },
      (state) => applyServerState(state),
    )
  } catch (e) {
    removeMessage(aiId)
    showToast(e.message || '发送失败，请稍后再试')
  } finally {
    chat.sending = false
    saveDraft() // 每轮落定即存草稿（FR-12）
    scrollToBottom()
  }
}

// 学生发送：先落消息、过硬规则（关键词切讲解 / 连续卡壳升梯度），再请求回复
async function onSend() {
  const text = input.value.trim()
  if (!text || chat.sending) return
  input.value = ''
  pushMessage('user', text)
  applyHardRules(text)
  scrollToBottom()
  await requestReply()
}

// 手动切换模式：AI 立即按新模式主动回复（7.5，不等学生再发言）
function onModeSwitch(mode) {
  if (chat.sending || mode === chat.state.mode) return
  setMode(mode) // 插入切换说明气泡并存草稿
  requestReply()
}

// 生成错题卡（FR-7）：成功即清对话草稿（FR-12），带卡跳错题卡页
const genLoading = ref(false)
async function onNote() {
  if (genLoading.value) return
  const msgs = apiMessages()
  if (msgs.length < 2) {
    showToast('先和教练聊几轮，再生成错题卡')
    return
  }
  genLoading.value = true
  showLoadingToast({ message: '正在生成错题卡…', duration: 0, forbidClick: true })
  try {
    const card = await noteGenerate(session.questionText, session.studentWork, msgs)
    session.pendingCard = card
    clearDraft()
    closeToast()
    router.push(`/card/${card.id}`)
  } catch (e) {
    closeToast()
    showToast(e.message || '生成失败，请稍后再试')
  } finally {
    genLoading.value = false
  }
}

// 进入页面：有草稿且非新核验 → 恢复续聊（FR-12）；否则开新对话
onMounted(() => {
  const draft = loadDraft()
  if (draft && draft.messages?.length && !session.verified) {
    // 刷新恢复：题目字段 + 消息 + 状态（原图 objectURL 已失效，不恢复）
    Object.assign(session, draft.question, { imageDataUrl: '' })
    // 必须经 pushMessage 重新分配自增 id——直接 push 旧 id 会与 seq 从 0 起的新消息撞车，
    // 流式增量会写进同 id 的旧消息，新气泡永远空白
    draft.messages.forEach((m) => pushMessage(m.role, m.content))
    chat.state = { ...draft.state }
    scrollToBottom()
  } else {
    // 新对话：清旧草稿；首次插入高亮说明气泡（三触点之一）；空会话自动发起 P1 开场
    clearDraft()
    resetChat()
    if (!localStorage.getItem(INTRO_SEEN_KEY)) {
      pushMessage('notice', '引导模式：我不会直接给答案，会一步步问你，带你找到错在哪。想直接听懂？点顶栏『讲解』。')
      localStorage.setItem(INTRO_SEEN_KEY, '1')
    }
    requestReply()
  }
})
</script>

<template>
  <div class="page chat">
    <van-nav-bar title="错题对话" fixed placeholder left-arrow @click-left="router.push('/')">
      <template #right>
        <span class="note-btn" @click="onNote">生成笔记</span>
      </template>
    </van-nav-bar>

    <!-- 顶栏「引导｜讲解」分段器（7.5 方案 A，常驻显眼） -->
    <div class="top-tools">
      <div class="seg">
        <button :class="{ active: chat.state.mode === 'guide' }" @click="onModeSwitch('guide')">引导</button>
        <button :class="{ active: chat.state.mode === 'direct' }" @click="onModeSwitch('direct')">讲解</button>
      </div>
      <button class="q-toggle" @click="showRef = !showRef">{{ showRef ? '收起题目' : '查看题目' }}</button>
    </div>

    <div class="chat-main">
      <!-- 题目 + 我的错答参考卡：手机端点开才显示，桌面端常驻左栏（3.5） -->
      <aside class="ref-card" :class="{ open: showRef }">
        <p class="ref-label">题目</p>
        <div class="ref-body" v-html="refQuestionHtml"></div>
        <template v-if="session.studentWork">
          <p class="ref-label">我的错答</p>
          <div class="ref-body wrong" v-html="refWorkHtml"></div>
        </template>
      </aside>

      <div ref="listEl" class="bubble-list">
        <div v-for="m in chat.messages" :key="m.id" class="row" :class="m.role">
          <div v-if="m.role === 'notice'" class="bubble notice">{{ m.content }}</div>
          <div v-else-if="m.role === 'user'" class="bubble user">{{ m.content }}</div>
          <div v-else class="bubble assistant" v-html="renderMixed(m.content)"></div>
        </div>
        <p v-if="thinking" class="thinking">教练正在思考…</p>
      </div>
    </div>

    <div class="input-bar">
      <input
        v-model="input"
        class="ipt"
        type="text"
        placeholder="说说你的思路，或问教练一个问题"
        @keydown.enter.prevent="onSend"
      />
      <van-button type="primary" :disabled="chat.sending || !input.trim()" @click="onSend">发送</van-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* 移动端地址栏收起时不溢出 */
  overflow: hidden;
}

.note-btn {
  color: var(--accent);
  font-size: 14px;
}

/* 顶栏工具行：模式分段器 + 手机端题目展开按钮 */
.top-tools {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 8px 16px 4px;
}

.seg {
  display: flex;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 999px;
  overflow: hidden;
}

.seg button {
  border: none;
  background: transparent;
  padding: 6px 24px;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
}

.seg button.active {
  background: var(--accent);
  color: #fff;
}

.q-toggle {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.chat-main {
  flex: 1;
  min-height: 0; /* flex 子项默认 min-height:auto，不加会导致内容撑开、滚动失效 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 题目参考卡：手机端点开才显示，桌面端常驻左栏 */
.ref-card {
  display: none;
  margin: 0 16px 8px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.ref-card.open {
  display: block;
}

.ref-label {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.ref-body {
  font-size: 14px;
  line-height: 1.7;
}

.ref-body.wrong {
  color: var(--wrong);
  text-decoration: underline dashed var(--wrong);
  text-underline-offset: 4px;
}

.bubble-list {
  flex: 1;
  min-height: 0; /* 同上：保证列表区域实际限高，滚动生效 */
  overflow-y: auto;
  padding: 8px 16px 16px;
}

.row {
  display: flex;
  margin-bottom: 12px;
}

.row.user {
  justify-content: flex-end;
}

.row.notice {
  justify-content: center;
}

.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 15px;
  line-height: 1.7;
  word-break: break-word;
  overflow-x: auto; /* 超长行内公式不可折行时在气泡内横向滚动，不溢出边界 */
}

.bubble.user {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.katex-block {
  margin: 6px 0;
  overflow-x: auto;
}

.bubble.notice {
  max-width: 94%;
  background: var(--highlight);
  color: #713f12;
  font-size: 13px;
  text-align: center;
  border-radius: 12px;
  padding: 8px 12px;
}

.thinking {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  background: var(--bg);
  border-top: 1px solid var(--border);
}

.ipt {
  flex: 1;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #fff;
  font-size: 15px;
  color: var(--text);
  outline: none;
}

.ipt:focus {
  border-color: var(--accent);
}

/* 桌面端：左栏参考卡常驻，对话流限宽 760px（3.5） */
@media (min-width: 768px) {
  .q-toggle {
    display: none;
  }

  .chat-main {
    flex-direction: row; /* 默认 stretch：右列撑满高度，气泡列表才能滚动 */
    gap: 20px;
    max-width: 1080px;
    width: 100%;
    margin: 0 auto;
    padding: 12px 24px 0;
  }

  .ref-card {
    display: block;
    width: 300px;
    flex-shrink: 0;
    align-self: flex-start; /* 参考卡不随行拉伸，自身限高滚动 */
    margin: 0;
    position: sticky;
    top: 12px;
    max-height: calc(100vh - 180px);
    overflow-y: auto;
  }

  .bubble-list {
    flex: 1;
    min-width: 0;
    max-width: 760px;
    margin: 0 auto;
  }
}
</style>
