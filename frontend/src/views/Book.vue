<script setup>
// 错题本（FR-9/12/13）：牌堆浏览（3.3）+ 维度切换 + 桌面表格视图 + 未完成对话入口
// 交互模型（3.3）：收拢态无悬停效果 → 点击牌堆向右推开 → 推开后悬停半抽预览 →
//                点击单张完全抽出（居中放大浮层展示详细内容）→ 点空白/放回收拢
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { loadDraft } from '../store/chat'
import { renderMixed } from '../utils/render'

const router = useRouter()

const cards = ref([])
const hasDraft = ref(false)
const draftPreview = ref('')

const DIMS = [
  { key: 'subject', label: '学科' },
  { key: 'wrong_reason', label: '错因类型' },
  { key: 'knowledge_points', label: '知识点' },
]
const dimension = ref('subject') // 默认按学科分堆（3.3）

const isDesktop = ref(window.matchMedia('(min-width: 768px)').matches)
const viewMode = ref(isDesktop.value ? 'table' : 'pile') // 桌面默认表格管理视图，手机牌堆（3.5）
function onResize() {
  isDesktop.value = window.matchMedia('(min-width: 768px)').matches
}
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => window.removeEventListener('resize', onResize))

function load() {
  cards.value = JSON.parse(localStorage.getItem('mc_cards') || '[]')
  const draft = loadDraft()
  hasDraft.value = !!draft
  draftPreview.value = draft?.question?.questionText?.slice(0, 40) || ''
}

function dimsOf(card, dim) {
  if (dim === 'subject') return [card.subject || '其他']
  if (dim === 'wrong_reason') return [card.wrong_reason?.category || '未分类']
  return card.knowledge_points?.length ? card.knowledge_points : ['未标注']
}

// 分堆：单堆最多 12 张，超出折叠为"更多"堆（3.3）
const groups = computed(() => {
  const map = new Map()
  cards.value.forEach((c) => {
    dimsOf(c, dimension.value).forEach((k) => {
      if (!map.has(k)) map.set(k, [])
      map.get(k).push(c)
    })
  })
  return [...map.entries()].map(([key, list]) => ({
    key,
    count: list.length,
    visible: list.slice(0, 12),
    overflow: list.slice(12),
  }))
})

// 牌堆交互状态：推开的堆 / 完全抽出（居中浮层）的卡 / 展开的"更多"堆
const spreadKey = ref('')
const drawnId = ref('')
const expandedKey = ref('')

function toggleSpread(key) {
  spreadKey.value = spreadKey.value === key ? '' : key
  drawnId.value = ''
}
// 两段式（3.3）：牌堆收拢时点牌=先推开；已推开后点牌=完全抽出（居中浮层）
function drawCard(card) {
  const g = groups.value.find((g) => g.visible.some((c) => c.id === card.id))
  const key = g?.key ?? ''
  if (spreadKey.value !== key) {
    spreadKey.value = key
    drawnId.value = ''
    return
  }
  drawnId.value = card.id
}
// 只收回浮层中的卡，牌堆保持推开态（方便继续浏览其他牌）
function closeOverlay() {
  drawnId.value = ''
}
function onBackdrop() {
  spreadKey.value = ''
  drawnId.value = ''
  expandedKey.value = ''
}
function toggleMore(key) {
  expandedKey.value = expandedKey.value === key ? '' : key
}

// 完全抽出的卡（浮层数据源：在全部卡中按 id 查找，避免多堆同卡重复）
const drawnCard = computed(() => cards.value.find((c) => c.id === drawnId.value) || null)
const drawnQuestionHtml = computed(() => (drawnCard.value ? renderMixed(drawnCard.value.question) : ''))
const drawnFinalHtml = computed(() => (drawnCard.value ? renderMixed(drawnCard.value.final_answer) : ''))

function goCard(card) {
  router.push(`/card/${card.id}`)
}

// 牌位姿：收拢=小错位叠放；推开=横向铺开（卡宽与间距随屏幕/张数自适应，顶牌先动逐张错开 22ms）
function wrapStyle(group, idx) {
  const n = group.visible.length
  if (!spreadKey.value || spreadKey.value !== group.key) {
    return { '--tx': `${idx * 4}px`, '--ty': `${idx * -3}px`, '--delay': '0ms', zIndex: idx + 1 }
  }
  const cardW = isDesktop.value ? 150 : 118
  const pileW = Math.min(760, window.innerWidth - 48)
  const gap = Math.min(isDesktop.value ? 64 : 36, Math.max(isDesktop.value ? 24 : 16, (pileW - cardW) / Math.max(1, n - 1)))
  return { '--tx': `${idx * gap}px`, '--ty': '0px', '--delay': `${(n - 1 - idx) * 22}ms`, zIndex: idx + 1 }
}

// 手机端"按住半抽"：按住卡牌立即浮起预览（模拟桌面 hover）；纵向滑动页面时取消
const pressedKey = ref('')
let touchStartXY = { x: 0, y: 0 }
function onCardTouchStart(e, key) {
  pressedKey.value = key
  touchStartXY = { x: e.touches[0].clientX, y: e.touches[0].clientY }
}
function onCardTouchMove(e) {
  const t = e.touches[0]
  const dx = Math.abs(t.clientX - touchStartXY.x)
  const dy = Math.abs(t.clientY - touchStartXY.y)
  if (dy > 12 && dy > dx * 1.5) {
    pressedKey.value = '' // 明确的纵向滚屏才取消，快速横滑的轻微抖动不影响
    return
  }
  // touch 事件的 target 固定在起点卡上，滑过的卡收不到事件——按手指坐标反查所在卡
  const el = document.elementFromPoint(t.clientX, t.clientY)?.closest('.pcard-wrap')
  const key = el?.dataset.peekKey
  if (key && el?.closest('.pile')?.classList.contains('spread')) {
    pressedKey.value = key
  } else {
    pressedKey.value = '' // 滑到空白/未推开的堆，收回落起
  }
}
function onCardTouchEnd() {
  pressedKey.value = ''
}

function summary(question) {
  return String(question || '').replace(/\$/g, '').slice(0, 64)
}
function dateOf(card) {
  return (card.created_at || '').slice(0, 10)
}

// ---- 示例数据（测试交互用）：数学卡 ×6，含 LaTeX ----
const DEMO_CARDS = [
  {
    id: 'demo-1', created_at: '2026-11-13T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['一元二次方程'],
    question: '解方程：$x^2 - 4x + 3 = 0$',
    student_wrong_answer: '我直接开方得到了 $x^2-4x=-3$，然后就卡住了',
    wrong_reason: { category: '方法缺失', analysis: '学生说"直接开方卡住了"，说明没有先尝试因式分解或配方法的意识' },
    correct_solution: ['移项：$x^2 - 4x = -3$', '因式分解：$(x-1)(x-3)=0$', '得 $x_1=1,\\ x_2=3$'],
    final_answer: '$x_1=1,\\ x_2=3$',
    variant_question: '解方程：$x^2 - 6x + 8 = 0$',
    variant_answer: '因式分解 $(x-2)(x-4)=0$，得 $x_1=2,\\ x_2=4$',
    insight_quote: '原来先因式分解两个根就出来了！', chat_summary: '从硬开方到学会因式分解求解。',
  },
  {
    id: 'demo-2', created_at: '2026-11-12T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['二次函数'],
    question: '求抛物线 $y = x^2 - 2x - 3$ 的顶点坐标与开口方向',
    student_wrong_answer: '我以为是 $(1,-3)$，把常数项当成了最低点',
    wrong_reason: { category: '概念不清', analysis: '学生把常数项当作顶点纵坐标，说"以为最低点就是 -3"，概念不清' },
    correct_solution: ['配方：$y = (x^2-2x+1) - 4$', '即 $y=(x-1)^2-4$', '顶点 $(1,-4)$，开口向上'],
    final_answer: '顶点 $(1,-4)$，开口向上',
    variant_question: '求 $y = x^2 + 4x + 5$ 的顶点坐标',
    variant_answer: '配方 $y=(x+2)^2+1$，顶点 $(-2,1)$',
    insight_quote: '原来配方就能看出顶点！', chat_summary: '补齐了配方法求顶点的思路。',
  },
  {
    id: 'demo-3', created_at: '2026-11-11T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['分式化简'],
    question: '化简：$\\frac{x^2-1}{x-1}$',
    student_wrong_answer: '我不会约分，分子分母看起来没有公因式',
    wrong_reason: { category: '方法缺失', analysis: '学生说"看不到公因式"，没想到先把分子因式分解' },
    correct_solution: ['分子因式分解：$x^2-1=(x+1)(x-1)$', '约去 $(x-1)$', '得 $x+1\\ (x \\neq 1)$'],
    final_answer: '$x+1\\ (x \\neq 1)$',
    variant_question: '化简：$\\frac{a^2-4}{a+2}$',
    variant_answer: '$\\frac{(a+2)(a-2)}{a+2}=a-2\\ (a \\neq -2)$',
    insight_quote: '先把分子因式分解再约分就通了！', chat_summary: '掌握先分解后约分的化简套路。',
  },
  {
    id: 'demo-4', created_at: '2026-11-10T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['圆的切线'],
    question: 'PA 是 $\\odot O$ 的切线，A 为切点，求 $\\angle OAB$ 与 $\\angle PAB$ 的关系（B 在圆上）',
    student_wrong_answer: '我以为切线和半径是平行的',
    wrong_reason: { category: '概念不清', analysis: '学生说"以为切线和半径平行"，混淆了切线性质' },
    correct_solution: ['切线性质：$OA \\perp PA$', '所以 $\\angle OAP = 90°$', '$\\angle OAB = 90° - \\angle PAB$'],
    final_answer: '$\\angle OAB + \\angle PAB = 90°$',
    variant_question: '切线 PA 切圆于 A，$\\angle PAB = 30°$，求 $\\angle OAB$',
    variant_answer: '$\\angle OAB = 90° - 30° = 60°$',
    insight_quote: '切线永远垂直于过切点的半径！', chat_summary: '记牢切线性质定理。',
  },
  {
    id: 'demo-5', created_at: '2026-11-09T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['概率初步'],
    question: '袋中有 3 个红球 2 个白球，除颜色外相同。一次摸出 2 个球，都是红球的概率是多少？',
    student_wrong_answer: '我算成 $\\frac{3}{5} \\times \\frac{3}{5} = \\frac{9}{25}$',
    wrong_reason: { category: '概念不清', analysis: '学生说"每次都是五分之三"，没意识到第一次摸出后袋中构成变了（不放回）' },
    correct_solution: ['第一次摸红：$\\frac{3}{5}$', '第二次摸红（剩 2 红 2 白）：$\\frac{2}{4}$', '相乘：$\\frac{3}{5} \\times \\frac{2}{4} = \\frac{3}{10}$'],
    final_answer: '$\\frac{3}{10}$',
    variant_question: '摸出 2 个球，一红一白的概率是多少？',
    variant_answer: '$2 \\times \\frac{3}{5} \\times \\frac{2}{4} = \\frac{3}{5}$（红白或白红两种顺序）',
    insight_quote: '第一次摸完袋子里的构成变了！', chat_summary: '理解不放回抽取的分步概率。',
  },
  {
    id: 'demo-6', created_at: '2026-11-08T10:00:00Z', subject: '数学', grade_band: '初中',
    knowledge_points: ['全等三角形'],
    question: '已知 AB=AC，AD 平分 ∠BAC 交 BC 于 D，说明 △ABD ≌ △ACD 的判定依据',
    student_wrong_answer: '我用了"边边角"来说明全等',
    wrong_reason: { category: '审题偏差', analysis: '学生说"我用了边边角"，忽略了 SSA 不是有效判定，而这里实为 SAS（AD 平分角给出夹角相等）' },
    correct_solution: ['$AB=AC$（已知）', '$\\angle BAD=\\angle CAD$（角平分线）', '$AD=AD$（公共边）', 'SAS 判定全等'],
    final_answer: '判定依据是 SAS（两边及夹角）',
    variant_question: '若改为 AD 是 BC 边上的中线，其他条件不变，还能判定全等吗？',
    variant_answer: '可以：$BD=CD$，用 SSS（$AB=AC$、$BD=CD$、$AD=AD$）判定',
    insight_quote: '原来是夹角，不是随便一个角！', chat_summary: '分清 SAS 与无效的 SSA。',
  },
]

function fillDemo() {
  const existing = JSON.parse(localStorage.getItem('mc_cards') || '[]')
  const ids = new Set(existing.map((c) => c.id))
  const toAdd = DEMO_CARDS.filter((c) => !ids.has(c.id))
  if (!toAdd.length) {
    showToast('示例卡已在错题本中')
    return
  }
  existing.unshift(...toAdd)
  localStorage.setItem('mc_cards', JSON.stringify(existing))
  load()
  showToast(`已添加 ${toAdd.length} 张示例卡`)
}

function clearAll() {
  showConfirmDialog({
    title: '清空错题本',
    message: '将删除全部错题卡（含示例卡），不可恢复。确定吗？',
  })
    .then(() => {
      localStorage.removeItem('mc_cards')
      load()
      showToast('已清空')
    })
    .catch(() => {})
}
</script>

<template>
  <div class="page book">
    <van-nav-bar title="错题本" fixed placeholder left-arrow @click-left="router.push('/')" />

    <div class="content" @click="onBackdrop">
      <!-- 未完成对话入口（FR-12） -->
      <button v-if="hasDraft" class="draft-banner" @click="router.push('/chat')">
        <span class="draft-title">继续上次对话</span>
        <span class="draft-preview">{{ draftPreview }}</span>
        <van-icon name="arrow" />
      </button>

      <div class="tools">
        <div class="seg">
          <button
            v-for="d in DIMS"
            :key="d.key"
            :class="{ active: dimension === d.key }"
            @click="dimension = d.key; onBackdrop()"
          >
            {{ d.label }}
          </button>
        </div>
        <div class="tools-right">
          <div v-if="isDesktop" class="seg view-seg">
            <button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">表格</button>
            <button :class="{ active: viewMode === 'pile' }" @click="viewMode = 'pile'">牌堆</button>
          </div>
          <button class="mini-btn" @click="fillDemo">填充示例</button>
          <button v-if="cards.length" class="mini-btn danger" @click="clearAll">清空</button>
        </div>
      </div>

      <van-empty v-if="!cards.length" description="还没有错题卡">
        <van-button type="primary" round @click="router.push('/')">去拍第一道错题</van-button>
      </van-empty>

      <!-- 牌堆视图 -->
      <template v-else-if="viewMode === 'pile'">
        <div v-for="g in groups" :key="g.key" class="pile-block">
          <div class="pile-head" @click.stop="toggleSpread(g.key)">
            <span class="pile-name">{{ g.key }}</span>
            <span class="pile-count">{{ g.count }} 张</span>
          </div>
          <div class="pile" :class="{ spread: spreadKey === g.key }">
            <div
              v-for="(c, idx) in g.visible"
              :key="c.id + g.key"
              class="pcard-wrap"
              :class="{ peek: pressedKey === c.id + g.key }"
              :data-peek-key="c.id + g.key"
              :style="wrapStyle(g, idx)"
              @click.stop="drawCard(c)"
              @touchstart="onCardTouchStart($event, c.id + g.key)"
              @touchmove="onCardTouchMove"
              @touchend="onCardTouchEnd"
              @touchcancel="onCardTouchEnd"
            >
              <div class="pcard">
                <div class="pcard-pills">
                  <span class="pill">{{ c.subject }}</span>
                  <span v-if="c.knowledge_points?.[0]" class="pill soft">{{ c.knowledge_points[0] }}</span>
                </div>
                <p class="pcard-date">{{ dateOf(c) }}</p>
                <span class="pill reason">{{ c.wrong_reason?.category }}</span>
                <span class="pcard-tip">点击抽出</span>
              </div>
            </div>
          </div>

          <!-- 超出 12 张折叠为"更多"堆 -->
          <div v-if="g.overflow.length" class="more-pile" @click.stop="toggleMore(g.key)">
            更多 {{ g.overflow.length }} 张
          </div>
          <div v-if="expandedKey === g.key" class="more-list">
            <button v-for="c in g.overflow" :key="c.id" class="more-item" @click.stop="goCard(c)">
              <span class="pill">{{ c.subject }}</span>
              <span class="more-q">{{ summary(c.question) }}</span>
              <span class="more-date">{{ dateOf(c) }}</span>
            </button>
          </div>
        </div>
        <p class="pile-hint">点牌堆推开 · 按住/悬停半抽 · 点单张抽出详看 · 点空白收拢</p>
      </template>

      <!-- 桌面表格管理视图（3.5） -->
      <div v-else class="table-view">
        <div class="trow thead">
          <span>日期</span><span>学科</span><span>错因</span><span>知识点</span><span>题目摘要</span><span></span>
        </div>
        <button v-for="c in cards" :key="c.id" class="trow" @click="goCard(c)">
          <span>{{ dateOf(c) }}</span>
          <span><span class="pill">{{ c.subject }}</span></span>
          <span>{{ c.wrong_reason?.category }}</span>
          <span class="kp">{{ c.knowledge_points?.join('、') || '—' }}</span>
          <span class="q">{{ summary(c.question) }}</span>
          <span class="go">查看 →</span>
        </button>
      </div>
    </div>

    <!-- 完全抽出：居中放大浮层（3.3）；点空白只收回卡，牌堆保持推开 -->
    <div v-if="drawnCard" class="overlay" @click="closeOverlay">
      <div class="overlay-card" @click.stop>
        <header class="card-head">
          <div class="pills">
            <span class="pill">{{ drawnCard.subject }}</span>
            <span v-for="k in drawnCard.knowledge_points" :key="k" class="pill soft">{{ k }}</span>
            <span class="pill reason">{{ drawnCard.wrong_reason?.category }}</span>
          </div>
          <span class="date">{{ dateOf(drawnCard) }}</span>
        </header>
        <div class="ov-question" v-html="drawnQuestionHtml"></div>
        <div v-if="drawnCard.final_answer" class="ov-final">
          <span class="ov-label">答案</span>
          <span class="ov-final-body" v-html="drawnFinalHtml"></span>
        </div>
        <div class="ov-actions">
          <van-button type="primary" size="small" round @click="goCard(drawnCard)">查看完整错题卡</van-button>
          <van-button size="small" round plain @click="closeOverlay">放回牌堆</van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.content {
  max-width: 760px;
  margin: 0 auto;
  padding: 12px 16px 40px;
}

.draft-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #fff;
  border: 1.5px solid var(--accent);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
}

.draft-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}

.draft-preview {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
}

.tools-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.mini-btn.danger {
  color: var(--wrong);
  border-color: rgba(220, 38, 38, 0.35);
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
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

.seg button.active {
  background: var(--accent);
  color: #fff;
}

.pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fde68a;
  color: #92400e;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.pill.soft {
  background: #fef3c7;
}

.pill.reason {
  background: #fde68a;
}

/* ---- 牌堆（3.3） ---- */
.pile-block {
  margin-bottom: 24px;
}

.pile-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.pile-name {
  font-size: 15px;
  font-weight: 700;
}

.pile-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.pile {
  position: relative;
  height: 168px;
}

.pcard-wrap {
  position: absolute;
  left: 0;
  top: 0;
  width: 118px;
  height: 168px;
  transform: translate(var(--tx, 0), calc(var(--ty, 0) + var(--lift, 0px)));
  transition: transform 0.3s cubic-bezier(0.34, 1.8, 0.64, 1);
  transition-delay: var(--delay, 0ms);
  cursor: pointer;
}

@media (min-width: 768px) {
  .pile {
    height: 200px;
  }

  .pcard-wrap {
    width: 150px;
    height: 200px;
  }
}

/* 悬停半抽：桌面端；按住半抽：手机端模拟 hover 预览（3.3） */
/* 浮起跟手：清掉推开用的级联 delay，用更快的过渡（否则滑太快时动画还没开始） */
@media (hover: hover) and (min-width: 768px) {
  .pile.spread .pcard-wrap:hover {
    --lift: -16px;
    transition-delay: 0ms;
    transition-duration: 0.15s;
  }
}

.pile.spread .pcard-wrap.peek {
  --lift: -16px;
  transition-delay: 0ms;
  transition-duration: 0.15s;
}

.pile.spread .pcard-wrap.peek .pcard {
  box-shadow: 0 8px 18px rgba(217, 119, 6, 0.2);
}

.pcard {
  width: 100%;
  height: 100%;
  background: #fffdf6;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 10px;
  box-shadow: 0 3px 10px rgba(161, 98, 7, 0.12);
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
}

.pile.spread .pcard-wrap:hover .pcard {
  box-shadow: 0 8px 18px rgba(217, 119, 6, 0.2);
}

.pcard-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pcard-date {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
}

.pill.reason {
  align-self: flex-start;
}

.pcard-tip {
  margin-top: auto;
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.more-pile {
  display: inline-block;
  margin: -30px 0 0 12px;
  padding: 8px 14px;
  background: #fff;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  position: relative;
  z-index: 1;
}

.more-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.more-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
}

.more-q {
  flex: 1;
  font-size: 13px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-date {
  font-size: 11px;
  color: var(--text-secondary);
}

.pile-hint {
  margin: 4px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.7;
}

/* ---- 桌面表格视图（3.5） ---- */
.table-view {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.trow {
  display: grid;
  grid-template-columns: 80px 70px 90px 1fr 2fr 70px;
  gap: 8px;
  align-items: center;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-bottom: 1px solid var(--border);
  background: transparent;
  font-size: 13px;
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.trow:last-child {
  border-bottom: none;
}

.trow.thead {
  background: var(--bg);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: default;
}

.trow:not(.thead):hover {
  background: #fef6e0;
}

.trow .q {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trow .kp {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trow .go {
  color: var(--accent);
  white-space: nowrap;
}

/* ---- 完全抽出浮层（3.3）：居中放大展示详细内容 ---- */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(68, 64, 60, 0.45);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.overlay-card {
  width: min(560px, 92vw);
  max-height: 82vh;
  overflow-y: auto;
  background: #fffdf6;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  animation: card-pop 0.16s ease-out;
}

@keyframes card-pop {
  from {
    transform: scale(0.92);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .overlay-card {
    animation: none;
  }
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.date {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.ov-question {
  font-size: 15px;
  line-height: 1.8;
  word-break: break-word;
  background: #fff;
  border: 1px dashed var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.ov-question :deep(.katex-block) {
  overflow-x: auto;
}

.ov-final {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
  margin-bottom: 14px;
  word-break: break-word;
}

.ov-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

.ov-final-body :deep(.katex) {
  font-size: 1em;
}

.ov-actions {
  display: flex;
  gap: 10px;
}
</style>
