/** Supabase 客户端（登录注册 + 错题卡云端同步）。
 *  Publishable key 设计上就是公开的（放浏览器安全，数据安全靠数据库 RLS 策略兜底）；
 *  Secret key 只在后端环境变量里，绝不出现这里。 */
import { createClient } from '@supabase/supabase-js'

export const SUPABASE_URL = 'https://gpciehxlygmobmezbjpd.supabase.co'
export const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_hxn5HHap3GCVh7SfGqU8Zg_T3uiaGgL'

export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    storageKey: 'mc_supabase_auth', // 与项目其他 localStorage 键共用 mc_ 前缀
    persistSession: true,
  },
})
