import { createRouter, createWebHistory } from 'vue-router'
import { session } from '../store/session'
import { loadDraft } from '../store/chat'
import ShootView from '../views/Shoot.vue'
import VerifyView from '../views/Verify.vue'
import ChatView from '../views/Chat.vue'
import CardView from '../views/Card.vue'
import BookView from '../views/Book.vue'
import SettingsView from '../views/Settings.vue'

// 六路由 + 守卫（3.4）
const routes = [
  { path: '/', name: 'shoot', component: ShootView, meta: { title: '拍题' } },
  { path: '/verify', name: 'verify', component: VerifyView, meta: { title: '确认题目' } },
  { path: '/chat', name: 'chat', component: ChatView, meta: { title: '错题对话' } },
  { path: '/card/:id', name: 'card', component: CardView, meta: { title: '错题卡' } },
  { path: '/book', name: 'book', component: BookView, meta: { title: '错题本' } },
  { path: '/settings', name: 'settings', component: SettingsView, meta: { title: '设置' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  // /verify：识别数据仅在内存，刷新/直访回拍题页
  if (to.name === 'verify' && !session.imageDataUrl) return { name: 'shoot' }
  // /chat：核验通过或有草稿即可进入（FR-12 草稿续聊；3.4）
  if (to.name === 'chat' && !session.verified && !loadDraft()) return { name: 'shoot' }
  // /card/:id：错题本查有此卡，或是刚生成待保存的新卡（M3）
  if (to.name === 'card') {
    const cards = JSON.parse(localStorage.getItem('mc_cards') || '[]')
    const known = cards.some((c) => c.id === to.params.id) || session.pendingCard?.id === to.params.id
    if (!known) return { name: 'book' }
  }
})

// 逐页同步页面标题（3.4）
router.afterEach((to) => {
  document.title = to.meta.title || 'MistakeCoach'
})

export default router
