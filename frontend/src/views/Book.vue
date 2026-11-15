<script setup>
// 错题本（FR-9/12/13）：牌堆浏览（3.3）+ 维度切换 + 桌面表格视图 + 未完成对话入口
// 交互模型（3.3）：收拢态无悬停效果 → 点击牌堆向右推开 → 推开后悬停半抽预览 →
//                点击单张完全抽出（居中放大浮层展示详细内容）→ 点空白/放回收拢
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { syncCards } from '../api'
import { listDrafts } from '../store/chat'
import { useAuth } from '../store/auth'
import { renderMixed } from '../utils/render'

const router = useRouter()

// 云端同步（登录用户）：未登录（游客模式）该功能不可见，应用行为与此前一致
const { user } = useAuth()
const syncing = ref(false)

const cards = ref([])
const ongoing = ref([]) // 进行中的对话（尚未生成错题卡的会话桶）：最近更新在前，最多展示 3 条
const draftSids = ref(new Set()) // 全部现存会话桶 id：判断某张卡是否还有可回访的对话

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
onUnmounted(() => window.removeEventListener('resize', onResize))

function load() {
  cards.value = JSON.parse(localStorage.getItem('mc_cards') || '[]')
  const drafts = listDrafts()
  draftSids.value = new Set(drafts.map((d) => d.sid))
  // 已生成错题卡的会话从"进行中"隐藏——它的入口在卡片浮层的「继续这题的对话」，避免两个入口指向同一题
  const carded = new Set(cards.value.map((c) => c.sessionId).filter(Boolean))
  ongoing.value = drafts.filter((d) => !carded.has(d.sid)).slice(0, 3)
}

// 继续进行中的对话：带会话桶 id 进入，恢复对应题的对话
function goDraft(d) {
  router.push({ name: 'chat', query: { sid: d.sid } })
}

function draftPreviewOf(d) {
  return d.question?.questionText?.slice(0, 40) || ''
}

function timeOf(ts) {
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// 卡片能否回访对话：卡上记着 sessionId 且对应会话桶还在（桶超上限被裁剪过就没有了）
function cardHasChat(card) {
  return !!card?.sessionId && draftSids.value.has(card.sessionId)
}

// 从卡片浮层回到这道题的对话：历史消息与状态原样恢复
function goChatCard(card) {
  router.push({ name: 'chat', query: { sid: card.sessionId } })
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
// 抽出时记下被点牌的位置与左右邻牌：FLIP 的飞入起点 / 放回时的飞回终点与让位对象
const flyFrom = ref(null)
const flyPrevId = ref('')
const flyNextId = ref('')
function drawCard(card, e) {
  const g = groups.value.find((g) => g.visible.some((c) => c.id === card.id))
  const key = g?.key ?? ''
  if (spreadKey.value !== key) {
    spreadKey.value = key
    drawnId.value = ''
    return
  }
  const i = g.visible.findIndex((c) => c.id === card.id)
  flyPrevId.value = g.visible[i - 1]?.id || ''
  flyNextId.value = g.visible[i + 1]?.id || ''
  flyFrom.value = e.currentTarget.getBoundingClientRect()
  drawnId.value = card.id
}

// 抽出/放回过渡（WAAPI 三段路径）：抽出=牌朝屏幕中央方向横滑 35% 路程并捻转 10deg
// （旋转方向跟随横移方向，像手指捻出），再飞向中央放大转正；放回反向。页面不做暗遮罩
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
function onOverlayEnter(el) {
  const from = flyFrom.value
  if (!from || reducedMotion) return
  const to = el.getBoundingClientRect()
  const dx = from.left + from.width / 2 - (to.left + to.width / 2)
  const dy = from.top + from.height / 2 - (to.top + to.height / 2)
  const s = from.width / to.width
  const rot = dx > 0 ? -10 : 10
  el.animate(
    [
      { transform: `translate(${dx}px, ${dy}px) scale(${s})` },
      {
        transform: `translate(${dx * 0.65}px, ${dy - 10}px) scale(${s * 1.06}) rotate(${rot}deg)`,
        offset: 0.4,
        easing: 'cubic-bezier(0.45, 0, 0.55, 1)',
      },
      { transform: 'none' },
    ],
    { duration: 680, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
  )
}

function onOverlayLeave(el, done) {
  const to = flyFrom.value
  if (!to || reducedMotion) {
    done()
    return
  }
  const from = el.getBoundingClientRect()
  const dx = to.left + to.width / 2 - (from.left + from.width / 2)
  const dy = to.top + to.height / 2 - (from.top + from.height / 2)
  const s = to.width / from.width
  const rot = dx > 0 ? -10 : 10
  const anim = el.animate(
    [
      { transform: 'none' },
      {
        transform: `translate(${dx * 0.65}px, ${dy - 10}px) scale(${s * 1.08}) rotate(${rot}deg)`,
        offset: 0.68,
        easing: 'cubic-bezier(0.45, 0, 0.55, 1)',
      },
      { transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: 1 },
    ],
    { duration: 440, easing: 'ease-in' },
  )
  anim.onfinish = () => {
    done()
    // 牌已塞回缝隙：清让位 → 左右邻牌回弹合拢，原位牌淡入，一起把它"夹住"
    flyPrevId.value = ''
    flyNextId.value = ''
  }
  anim.oncancel = () => {
    done()
    flyPrevId.value = ''
    flyNextId.value = ''
  }
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

// 牌位姿：收拢=小错位叠放；推开=横向铺开（卡宽与间距随屏幕/张数自适应，顶牌先动逐张错开 22ms）。
// 放回让位：抽出的牌要塞回缝隙，左右邻牌先拨开 18px（--way），插回后清空回弹合拢
function wrapStyle(group, idx, id = '') {
  const n = group.visible.length
  if (!spreadKey.value || spreadKey.value !== group.key) {
    // 收拢也级联（顶牌先回）：收回与推开对称，都有逐张归位动画
    return { '--tx': `${idx * 4}px`, '--ty': `${idx * -3}px`, '--delay': `${(n - 1 - idx) * 18}ms`, zIndex: idx + 1 }
  }
  const cardW = isDesktop.value ? 150 : 118
  const pileW = Math.min(760, window.innerWidth - 48)
  const gap = Math.min(isDesktop.value ? 64 : 36, Math.max(isDesktop.value ? 24 : 16, (pileW - cardW) / Math.max(1, n - 1)))
  const style = { '--tx': `${idx * gap}px`, '--ty': '0px', '--delay': `${(n - 1 - idx) * 22}ms`, zIndex: idx + 1 }
  if (id && id === flyPrevId.value) {
    style['--way'] = '-18px'
    style['--delay'] = '0ms'
  } else if (id && id === flyNextId.value) {
    style['--way'] = '18px'
    style['--delay'] = '0ms'
  }
  return style
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

// 云端同步：本地全量上传（云端按卡 id 幂等 upsert），云端有而本地没有的合并回来。
// 合并语义（非镜像）：本地删除不传播——两台设备场景下镜像会误删还没同步过的卡。
// silent=登录后自动触发：成功不弹提示、失败静默（手动点按钮才详细反馈）
async function doSync(silent = false) {
  if (syncing.value || !user.value) return
  syncing.value = true
  try {
    const local = JSON.parse(localStorage.getItem('mc_cards') || '[]')
    const remote = await syncCards(local)
    const have = new Set(local.map((c) => c.id))
    let added = 0
    for (const c of remote) {
      if (c?.id && !have.has(c.id)) {
        local.push(c)
        added++
      }
    }
    if (added) {
      localStorage.setItem('mc_cards', JSON.stringify(local))
      load()
    }
    if (!silent) showToast(`同步完成：本机 ${local.length} 张，从云端补回 ${added} 张`)
  } catch (e) {
    if (!silent) showToast(e.message || '同步失败，请稍后再试')
  } finally {
    syncing.value = false
  }
}

// 登录即自动同步（让"登录 = 账号数据"成立，不用手动点按钮）：
// onMounted 兜底"已登录刷新页面"，watch 兜底"在本页新登录/退出后再登录"
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
  if (user.value) doSync(true)
})
watch(user, (u) => {
  if (u) doSync(true)
})

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
      <!-- 进行中的对话入口（FR-12）：每题一个独立会话桶，按题目列出；点任意一条恢复对应题的对话 -->
      <div v-if="ongoing.length" class="draft-box">
        <div v-if="ongoing.length > 1" class="draft-box-head">进行中的对话（{{ ongoing.length }}）</div>
        <button v-for="d in ongoing" :key="d.sid" class="draft-banner" @click="goDraft(d)">
          <span v-if="ongoing.length === 1" class="draft-title">继续上次对话</span>
          <span class="draft-preview">{{ draftPreviewOf(d) }}</span>
          <span v-if="ongoing.length > 1" class="draft-time">{{ timeOf(d.updatedAt) }}</span>
          <van-icon name="arrow" />
        </button>
      </div>

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
          <van-button
            v-if="user && cards.length"
            size="small"
            round
            plain
            class="sync-btn"
            :loading="syncing"
            loading-text="同步中…"
            @click="doSync()"
          >同步云端</van-button>
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
              :class="{ peek: pressedKey === c.id + g.key, drawn: drawnId === c.id }"
              :data-peek-key="c.id + g.key"
              :style="wrapStyle(g, idx, c.id)"
              @click.stop="drawCard(c, $event)"
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

    <!-- 完全抽出：居中放大浮层（3.3）；点空白只收回卡，牌堆保持推开。
         抽出/放回 FLIP 过渡（JS hooks）：从被点牌的真实位置飞入中央、放回飞回原位 -->
    <transition :css="false" @enter="onOverlayEnter" @leave="onOverlayLeave">
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
            <van-button
              v-if="cardHasChat(drawnCard)"
              type="primary"
              size="small"
              round
              plain
              @click="goChatCard(drawnCard)"
            >继续这题的对话</van-button>
            <van-button type="primary" size="small" round @click="goCard(drawnCard)">查看完整错题卡</van-button>
            <van-button size="small" round plain @click="closeOverlay">放回牌堆</van-button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.content {
  max-width: 760px;
  margin: 0 auto;
  padding: 12px 16px 40px;
}

/* 进行中的对话入口：多条时竖排列表，间距由 draft-box 统一控制 */
.draft-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.draft-box-head {
  font-size: 12px;
  color: var(--text-secondary);
}

.draft-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
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

.draft-time {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap; /* 手机窄屏放不下时整体换行，不挤压按钮 */
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
  white-space: nowrap;
}

.mini-btn.danger {
  color: var(--wrong);
  border-color: rgba(220, 38, 38, 0.35);
}

/* 同步云端按钮：与 mini-btn 视觉对齐（小圆角胶囊、同字号） */
.sync-btn {
  border: 1px solid var(--accent);
  color: var(--accent);
  background: #fff;
  font-size: 12px;
  padding: 4px 10px;
  white-space: nowrap;
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
  white-space: nowrap; /* 按钮文字禁止折行 */
}

.seg button.active {
  background: var(--accent);
  color: #fff;
}

/* 手机：收紧内边距与字号，保证维度胶囊 + 清空一行放下 */
@media (max-width: 430px) {
  .seg button {
    padding: 5px 10px;
    font-size: 12px;
  }

  .mini-btn {
    padding: 4px 10px;
  }
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
  transform: translate(calc(var(--tx, 0px) + var(--way, 0px)), calc(var(--ty, 0px) + var(--lift, 0px)));
  transition:
    transform 0.3s cubic-bezier(0.34, 1.8, 0.64, 1),
    opacity 0.2s ease;
  transition-delay: var(--delay, 0ms), 0ms;
  cursor: pointer;
}

/* 抽出到浮层期间藏起原位牌（FLIP 飞入的"起点"就是它），放回时淡入归位 */
.pcard-wrap.drawn {
  opacity: 0;
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
/* 不做暗遮罩：背景全透明，页面保持原亮度，靠浮层自身阴影悬浮（点击浮层外空白=放回） */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

/* 竖版 3:4，与牌堆里的牌等比例（宽 118×168 / 150×200 ≈ 3:4）——抽出是"同一张牌放大" */
.overlay-card {
  width: min(360px, 86vw);
  aspect-ratio: 3 / 4;
  max-height: 82vh;
  overflow-y: auto;
  background: #fffdf6;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
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
  flex-direction: column; /* 竖版卡：按钮纵排全宽 */
  gap: 8px;
}

.ov-actions :deep(.van-button) {
  width: 100%;
}

.ov-actions :deep(.van-button + .van-button) {
  margin-left: 0; /* Vant 相邻按钮默认 margin-left，纵排下去掉 */
}
</style>
