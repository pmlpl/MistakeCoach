<script setup>
// 错题卡页（FR-7/8）：手账荧光渲染（3.2）+ html2canvas 长图导出 + 存入错题本
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { closeToast, showLoadingToast, showToast } from 'vant'
import html2canvas from 'html2canvas'
import { renderMixed } from '../utils/render'
import { session } from '../store/session'

const route = useRoute()
const router = useRouter()

const card = ref(null)
const saved = ref(false)

onMounted(() => {
  const id = route.params.id
  const cards = JSON.parse(localStorage.getItem('mc_cards') || '[]')
  const found = cards.find((c) => c.id === id)
  if (found) {
    card.value = found
    saved.value = true
  } else if (session.pendingCard?.id === id) {
    card.value = session.pendingCard // 刚生成、还没存入的卡
  }
})

const dateText = computed(() => (card.value?.created_at || '').slice(0, 10))
const questionHtml = computed(() => (card.value ? renderMixed(card.value.question) : ''))
const wrongHtml = computed(() => (card.value ? renderMixed(card.value.student_wrong_answer) : ''))
const solutionSteps = computed(() => (card.value ? card.value.correct_solution.map((s) => renderMixed(s)) : []))
const variantHtml = computed(() => (card.value ? renderMixed(card.value.variant_question) : ''))
const variantAnswerHtml = computed(() => (card.value ? renderMixed(card.value.variant_answer) : ''))
const showVariantAnswer = ref(false)

// 导出长图：等字体与公式就绪后再抓 DOM（3.2 防抖规则）
const exporting = ref(false)
async function exportPng() {
  if (exporting.value || !card.value) return
  exporting.value = true
  showLoadingToast({ message: '正在生成长图…', duration: 0, forbidClick: true })
  try {
    await document.fonts.ready
    await nextTick()
    const canvas = await html2canvas(document.getElementById('mistake-card'), {
      scale: 2,
      backgroundColor: '#FFFBEB',
    })
    const link = document.createElement('a')
    link.download = `MistakeCoach-${card.value.subject}-${dateText.value}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
    showToast('长图已保存')
  } catch {
    showToast('导出失败，请重试')
  } finally {
    exporting.value = false
    closeToast()
  }
}

// 存入错题本（FR-9）：写入 localStorage，之后可从错题本随时回看
function saveToBook() {
  if (!card.value || saved.value) return
  const cards = JSON.parse(localStorage.getItem('mc_cards') || '[]')
  cards.unshift(card.value)
  localStorage.setItem('mc_cards', JSON.stringify(cards))
  saved.value = true
  showToast('已存入错题本')
}
</script>

<template>
  <div class="page card-page">
    <van-nav-bar title="错题卡" fixed placeholder left-arrow @click-left="router.back()" />

    <div class="wrap">
      <div v-if="card" id="mistake-card" class="mistake-card">
        <div class="tape tape-l"></div>
        <div class="tape tape-r"></div>

        <!-- 1. 学科·知识点标签 + 日期 -->
        <header class="card-head">
          <div class="pills">
            <span class="pill">{{ card.subject }}</span>
            <span v-for="k in card.knowledge_points" :key="k" class="pill">{{ k }}</span>
          </div>
          <span class="date">{{ dateText }}</span>
        </header>

        <!-- 2. 题目 -->
        <section class="sec">
          <p class="sec-title">题目</p>
          <div class="sec-body question" v-html="questionHtml"></div>
        </section>

        <!-- 3. 我的错答（红笔虚线） -->
        <section v-if="card.student_wrong_answer" class="sec">
          <p class="sec-title">我的错答</p>
          <div class="sec-body wrong" v-html="wrongHtml"></div>
        </section>

        <!-- 4. 错因胶囊 + 一句话分析 -->
        <section class="sec">
          <p class="sec-title">错因</p>
          <div class="reason">
            <span class="pill">{{ card.wrong_reason.category }}</span>
            <p class="analysis">{{ card.wrong_reason.analysis }}</p>
          </div>
        </section>

        <!-- 5. 正确解法（分步编号） -->
        <section class="sec">
          <p class="sec-title">正确解法</p>
          <ol class="solution">
            <li v-for="(s, i) in solutionSteps" :key="i">
              <span class="step-no">{{ i + 1 }}</span>
              <div class="step-body" v-html="s"></div>
            </li>
          </ol>
        </section>

        <!-- 6. 顿悟原话（左侧强调竖条） -->
        <section v-if="card.insight_quote" class="sec">
          <p class="sec-title">顿悟一刻</p>
          <blockquote class="insight">{{ card.insight_quote }}</blockquote>
        </section>

        <!-- 7. 变式练习（默认折叠，点「做完对答案」展开） -->
        <section v-if="card.variant_question" class="sec">
          <p class="sec-title">变式练习</p>
          <div class="sec-body" v-html="variantHtml"></div>
          <button v-if="!showVariantAnswer" class="reveal-btn" @click="showVariantAnswer = true">
            做完对答案
          </button>
          <div v-else class="variant-answer" v-html="variantAnswerHtml"></div>
        </section>

        <!-- 8. 品牌水印 -->
        <footer class="watermark">MistakeCoach · 让每道错题都有交代</footer>
      </div>

      <van-empty v-else description="卡片不存在" />

      <div v-if="card" class="actions">
        <van-button type="primary" block :loading="exporting" @click="exportPng">保存长图</van-button>
        <van-button v-if="!saved" block plain type="primary" @click="saveToBook">存入错题本</van-button>
        <van-button v-else block plain @click="router.push('/book')">去错题本看看</van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 740px;
  margin: 0 auto;
  padding: 12px 16px 120px;
}

/* 手账荧光卡（3.2 皮肤 token） */
.mistake-card {
  position: relative;
  background: #fffdf6;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 26px 22px 18px;
  box-shadow: 0 4px 14px rgba(161, 98, 7, 0.08);
}

/* 胶带装饰 */
.tape {
  position: absolute;
  top: -10px;
  width: 86px;
  height: 26px;
  background: rgba(250, 204, 21, 0.45);
  transform: rotate(-6deg);
  border-radius: 2px;
}

.tape-l {
  left: 34px;
}

.tape-r {
  right: 34px;
  transform: rotate(5deg);
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  padding: 3px 10px;
  border-radius: 999px;
  background: #fde68a;
  color: #92400e;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.date {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.sec {
  margin-bottom: 16px;
}

.sec-title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 1px;
}

.sec-body {
  font-size: 15px;
  line-height: 1.8;
  word-break: break-word;
}

.sec-body :deep(.katex-block) {
  overflow-x: auto;
}

.question {
  background: #fff;
  border: 1px dashed var(--border);
  border-radius: 12px;
  padding: 10px 12px;
}

/* 错答：红笔虚线 */
.wrong {
  color: var(--wrong);
  text-decoration: underline dashed var(--wrong);
  text-decoration-thickness: 1px;
  text-underline-offset: 5px;
}

.reason {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.analysis {
  margin: 2px 0 0;
  flex: 1;
  font-size: 14px;
  line-height: 1.7;
}

.solution {
  margin: 0;
  padding: 0;
  list-style: none;
}

.solution li {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.step-no {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 3px;
}

.step-body {
  flex: 1;
  font-size: 14px;
  line-height: 1.8;
  word-break: break-word;
}

.step-body :deep(.katex-block) {
  overflow-x: auto;
}

.insight {
  margin: 0;
  padding: 4px 0 4px 12px;
  border-left: 4px solid var(--accent);
  color: #713f12;
  font-size: 14px;
  line-height: 1.7;
}

.reveal-btn {
  margin-top: 8px;
  padding: 6px 14px;
  border: 1px dashed var(--accent);
  border-radius: 999px;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
}

.variant-answer {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fff;
  border: 1px dashed var(--border);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.8;
  word-break: break-word;
}

.watermark {
  margin-top: 20px;
  text-align: center;
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.75;
  letter-spacing: 1px;
}

/* 操作栏：不进导出区域 */
.actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 10px;
  padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  background: var(--bg);
  border-top: 1px solid var(--border);
}

/* 桌面端：卡片居中竖版比例，操作按钮横排（3.5） */
@media (min-width: 768px) {
  .wrap {
    padding: 20px 24px 100px;
  }

  .actions {
    left: 50%;
    right: auto;
    transform: translateX(-50%);
    width: min(740px, 92vw);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: var(--radius) var(--radius) 0 0;
  }
}
</style>
