import { getKeys } from './store/keys'

/** 统一请求封装：非 2xx 时把后端 detail 变成可读错误抛出 */
async function request(path, options) {
  const res = await fetch(path, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : `请求失败（${res.status}）`
    throw new Error(msg)
  }
  return data
}

/** 访客自带 Key：随请求头发送（后端优先用请求头 Key，缺省回落 .env，见文档 3.6） */
function authHeaders() {
  const { zhipu = '', deepseek = '' } = getKeys()
  const h = {}
  if (zhipu) h['X-Zhipu-Key'] = zhipu
  if (deepseek) h['X-Deepseek-Key'] = deepseek
  return h
}

/** POST /api/recognize：multipart 图片 -> 识别 JSON */
export function recognizeImage(file) {
  const fd = new FormData()
  fd.append('image', file)
  return request('/api/recognize', { method: 'POST', body: fd, headers: authHeaders() })
}

/** POST /api/note：对话记录 -> 错题卡 JSON（6.3） */
export function noteGenerate(questionText, studentWork, transcript) {
  return request('/api/note', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ question_text: questionText, student_work: studentWork, transcript }),
  })
}

/** POST /api/chat：SSE 流式对话（6.2）。onDelta 逐字回调；onState 收回复末尾的状态事件。
 *  45 秒无任何数据（含流中断）→ 主动 abort 并抛可读错误，避免空气泡卡死 */
export async function chatStream(payload, onDelta, onState) {
  const controller = new AbortController()
  let timer
  const resetTimer = () => {
    clearTimeout(timer)
    timer = setTimeout(() => controller.abort(), 45000)
  }
  resetTimer()
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      const msg = typeof data.detail === 'string' ? data.detail : `请求失败（${res.status}）`
      throw new Error(msg)
    }
    // 手动逐行解析 SSE：按 \n\n 分帧、data: 前缀
    const handleFrame = (frame) => {
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (!data || data === '[DONE]') continue
        let obj
        try {
          obj = JSON.parse(data)
        } catch {
          continue // 跳过无法解析的帧
        }
        if (obj.error) throw new Error(obj.error) // 后端显式错误（如空回复）
        if (obj.delta) onDelta(obj.delta)
        if (obj.state) onState(obj.state)
      }
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let gotData = false
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      gotData = true
      resetTimer() // 有数据就重置无响应计时（覆盖流中途卡死）
      buf += decoder.decode(value, { stream: true })
      let i
      while ((i = buf.indexOf('\n\n')) !== -1) {
        handleFrame(buf.slice(0, i))
        buf = buf.slice(i + 2)
      }
    }
    if (buf) handleFrame(buf) // 兜底：流末尾缺 \n\n 的残帧
    if (!gotData) throw new Error('教练没有回应，请再试一次')
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('教练思考超时了，请再试一次')
    throw e
  } finally {
    clearTimeout(timer)
  }
}
