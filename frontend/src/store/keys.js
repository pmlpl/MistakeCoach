/** 访客自带 Key（BYOK）：仅存本机 localStorage，随请求头使用（3.6） */
const STORE_KEY = 'mc_keys'

export function getKeys() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || '{}')
  } catch {
    return {}
  }
}

export function saveKeys({ zhipu = '', deepseek = '', chatProvider = 'deepseek' }) {
  localStorage.setItem(
    STORE_KEY,
    JSON.stringify({
      zhipu: zhipu.trim(),
      deepseek: deepseek.trim(),
      chatProvider: chatProvider === 'zhipu' ? 'zhipu' : 'deepseek',
    }),
  )
}

export function clearKeys() {
  localStorage.removeItem(STORE_KEY)
}
