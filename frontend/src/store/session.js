/** 会话级内存状态：拍题 -> 核验 -> 对话 之间的数据载体（刷新即清空，见 3.4） */
import { reactive } from 'vue'

export const session = reactive({
  imageDataUrl: '', // 原图预览（内存 objectURL，仅核验页展示用）
  subject: '其他',
  gradeBand: '初中',
  questionText: '', // 核验后的题目原文（对话/笔记一律以此为准）
  studentWork: '', // 核验后的学生错误作答
  hasHandwriting: false,
  verified: false, // 核验页确认后才允许进入对话
  pendingCard: null, // 刚生成、尚未存入错题本的卡（内存态，刷新即丢）
})

export function resetSession() {
  Object.assign(session, {
    imageDataUrl: '',
    subject: '其他',
    gradeBand: '初中',
    questionText: '',
    studentWork: '',
    hasHandwriting: false,
    verified: false,
  })
}
