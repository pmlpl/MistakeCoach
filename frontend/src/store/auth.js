/** 登录状态（Supabase Auth）：响应式 user/ready 全局单例。
 *  游客模式不受影响——user 为 null 时应用行为与此前完全一致。 */
import { ref } from 'vue'
import { supabase } from '../lib/supabase'

const user = ref(null)
const ready = ref(false) // 初始 session 是否已从 localStorage 恢复（防登录态闪跳）

supabase.auth.getSession().then(({ data }) => {
  user.value = data.session?.user || null
  ready.value = true
})

// 跨标签页/令牌刷新/登出统一走这里，user 永远等于最新状态
supabase.auth.onAuthStateChange((_event, s) => {
  user.value = s?.user || null
  ready.value = true
})

export function useAuth() {
  return { user, ready }
}

export async function signUp(email, password) {
  const { data, error } = await supabase.auth.signUp({ email, password })
  if (error) throw error
  // 项目关闭了邮箱确认 → data.session 直接就绪（已登录）；开着则提示去收信
  return { needsEmailConfirm: !data.session }
}

export async function signIn(email, password) {
  const { error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) throw error
}

export async function signOut() {
  await supabase.auth.signOut()
}

/** 当前登录用户的 access token（调后端同步接口用）；未登录返回 null。
 *  access token 只有 1 小时有效期：页面切后台时 supabase-js 的自动续期定时器会被浏览器
 *  节流暂停，回到页面后 token 可能已过期——所以在取出前主动检查并 refreshSession */
export async function accessToken() {
  let { data } = await supabase.auth.getSession()
  let session = data.session
  if (session) {
    const expiresAt = session.expires_at || 0 // 秒级时间戳
    if (expiresAt < Math.floor(Date.now() / 1000) + 30) {
      // 已过期或 30 秒内将过期：用 refresh_token 换新 token（refreshSession 失败则沿用旧值，让后端报错）
      const { data: refreshed } = await supabase.auth.refreshSession()
      session = refreshed.session || session
    }
  }
  return session?.access_token || null
}
