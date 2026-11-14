/** 统一的「文本 + 数学公式」混排渲染（对话气泡 / 核验预览 / 错题卡共用） */
import katex from 'katex'
import 'katex/dist/katex.min.css'

export function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/**
 * 混排渲染：先归一模型可能输出的多种公式定界符（\(…\) 与 \[…\] → $…$ / $$…$$），
 * 再分段走 KaTeX；**加粗**转 strong；换行/加粗只处理纯文本段——
 * 必须在 KaTeX 渲染之外做，否则 <br> 会混进 KaTeX 生成的 SVG path 属性里打碎公式。
 */
export function renderMixed(text) {
  if (!text) return ''
  const unified = text
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, g) => `$${g}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, g) => `$$${g}$$`)
  return unified
    .split(/\$\$([\s\S]+?)\$\$/g)
    .map((seg, i) => {
      if (i % 2) {
        return `<div class="katex-block">${katex.renderToString(seg, { throwOnError: false, displayMode: true })}</div>`
      }
      return seg
        .split(/\$(.+?)\$/g)
        .map((s, j) => {
          if (j % 2) return katex.renderToString(s, { throwOnError: false })
          return esc(s)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>')
        })
        .join('')
    })
    .join('')
}
