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

/** 当前登录用户的 access token（调后端同步接口用）；未登录返回 null */
export async function accessToken() {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token || null
}
