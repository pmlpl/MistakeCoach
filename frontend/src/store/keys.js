/** 访客自带 Key 与模型配置（BYOK）：仅存本机 localStorage，随请求使用（3.6）
 *  所有供应商走 OpenAI 兼容接口（Claude/Gemini 用官方兼容层），后端只实现一条通道 */
const STORE_KEY = 'mc_keys'

/** 供应商预设：base 为 OpenAI 兼容基底（后端拼 /chat/completions）
 *  vision/chat 为该家默认模型名；keyFrom='self' 表示需在本卡独立填 Key，
 *  'zhipu'/'deepseek' 表示复用公共 Key 输入框里的对应 Key */
export const PROVIDERS = {
  zhipu: { label: '智谱 GLM·免费', base: 'https://open.bigmodel.cn/api/paas/v4', vision: 'glm-4v-flash', chat: 'glm-4.7-flash', keyFrom: 'zhipu' },
  deepseek: { label: 'DeepSeek', base: 'https://api.deepseek.com', vision: 'deepseek-flash', chat: 'deepseek-chat', keyFrom: 'deepseek' },
  openai: { label: 'OpenAI', base: 'https://api.openai.com/v1', vision: 'gpt-4o-mini', chat: 'gpt-4o-mini', keyFrom: 'self' },
  anthropic: { label: 'Claude', base: 'https://api.anthropic.com/v1', vision: 'claude-sonnet-4-5', chat: 'claude-sonnet-4-5', keyFrom: 'self' },
  gemini: { label: 'Gemini', base: 'https://generativelanguage.googleapis.com/v1beta/openai', vision: 'gemini-2.5-flash', chat: 'gemini-2.5-flash', keyFrom: 'self' },
  custom: { label: '自定义', base: '', vision: '', chat: '', keyFrom: 'self' },
}

export function getKeys() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || '{}')
  } catch {
    return {}
  }
}

/** 存储结构：{ zhipu, deepseek, recognize: {provider, model, baseUrl, key}, chat: {...} } */
export function saveKeys({ zhipu = '', deepseek = '', recognize = {}, chat = {} }) {
  const norm = (m, def) => ({
    provider: PROVIDERS[m?.provider] ? m.provider : def,
    model: (m?.model || '').trim(),
    baseUrl: (m?.baseUrl || '').trim(),
    key: (m?.key || '').trim(),
  })
  localStorage.setItem(
    STORE_KEY,
    JSON.stringify({
      zhipu: zhipu.trim(),
      deepseek: deepseek.trim(),
      recognize: norm(recognize, 'zhipu'),
      chat: norm(chat, 'deepseek'),
    }),
  )
}

export function clearKeys() {
  localStorage.removeItem(STORE_KEY)
}

/** 解析某用途（'recognize' | 'chat'）的最终模型配置；兼容旧版存储（只有 zhipu/deepseek/chatProvider）
 *  返回 {provider, model, baseUrl, key}——key 为空表示还没配好 */
export function modelConfig(purpose) {
  const raw = getKeys()
  const stored = raw[purpose]
  const legacyChatProvider = raw.chatProvider === 'zhipu' ? 'zhipu' : 'deepseek'
  const m =
    stored && PROVIDERS[stored.provider]
      ? stored
      : { provider: purpose === 'chat' ? legacyChatProvider : 'zhipu', model: '', baseUrl: '', key: '' }
  const preset = PROVIDERS[m.provider] || PROVIDERS.zhipu
  const model = m.model || (purpose === 'chat' ? preset.chat : preset.vision) || ''
  const baseUrl = m.baseUrl || preset.base || ''
  // Key：本卡独立 Key 优先；智谱/DeepSeek 预设复用公共 Key 输入框里的值
  let key = m.key
  if (!key && preset.keyFrom === 'zhipu') key = raw.zhipu || ''
  if (!key && preset.keyFrom === 'deepseek') key = raw.deepseek || ''
  return { provider: m.provider, model, baseUrl, key }
}
