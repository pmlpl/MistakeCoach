<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { closeToast, showImagePreview, showLoadingToast, showToast } from 'vant'
import { recognizeImage } from '../api'
import { compressImage } from '../utils/image'
import { renderMixed } from '../utils/render'
import { resetSession, session } from '../store/session'

const router = useRouter()

const subjects = ['数学', '物理', '化学', '语文', '英语', '其他']
const grades = ['初中', '高中']

// 公式预览：与对话气泡同一套混排渲染（兼容 $…$，简记原文直接展示，3.1 边改边看）
const previewHtml = computed(() => renderMixed(session.questionText))

// 智能提醒：题干为空或 <10 字禁止进入对话（3.1）
const questionTooShort = computed(() => session.questionText.trim().length < 10)

function confirm() {
  if (questionTooShort.value) return
  session.verified = true
  router.push('/chat')
}

function retake() {
  resetSession()
  router.push('/')
}

// ---- 圈选重识：AI 选错题时，手动框住要问的那道题，裁剪后重新识别 ----
const imgEl = ref(null)
const cropMode = ref(false) // 是否处于圈选模式
const cropping = ref(false) // 正在拖框
const cropBox = ref(null) // { x, y, w, h } 相对图片显示区的 px
let dragStart = null
let dragRect = null

const boxStyle = computed(() => {
  const b = cropBox.value
  return b ? { left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, height: `${b.h}px` } : {}
})

function toggleCrop() {
  cropMode.value = !cropMode.value
  cropBox.value = null
}

function onPhotoClick() {
  if (cropMode.value) return // 圈选时点击不再放大预览
  showImagePreview({ images: [session.imageDataUrl], closeable: true, closeOnPopstate: true, showIndex: false })
}

function onCropDown(e) {
  if (!cropMode.value) return
  dragRect = imgEl.value.getBoundingClientRect()
  dragStart = { x: e.clientX - dragRect.left, y: e.clientY - dragRect.top }
  cropBox.value = { x: dragStart.x, y: dragStart.y, w: 0, h: 0 }
  cropping.value = true
  imgEl.value.setPointerCapture?.(e.pointerId) // 拖出图片仍能收到 move/up
}

function onCropMove(e) {
  if (!cropping.value) return
  const x = Math.min(Math.max(e.clientX - dragRect.left, 0), dragRect.width)
  const y = Math.min(Math.max(e.clientY - dragRect.top, 0), dragRect.height)
  cropBox.value = {
    x: Math.min(dragStart.x, x),
    y: Math.min(dragStart.y, y),
    w: Math.abs(x - dragStart.x),
    h: Math.abs(y - dragStart.y),
  }
}

async function onCropUp() {
  if (!cropping.value) return
  cropping.value = false
  const b = cropBox.value
  if (!b || b.w < 40 || b.h < 40) {
    cropBox.value = null // 太小视为误触
    return
  }
  await reRecognize(b)
}

async function reRecognize(box) {
  const img = imgEl.value
  const natW = img.naturalWidth
  const natH = img.naturalHeight
  // object-fit: contain：显示框与实际绘制区存在留白偏移，先映射回原图像素坐标
  const scale = Math.min(img.clientWidth / natW, img.clientHeight / natH)
  const offX = (img.clientWidth - natW * scale) / 2
  const offY = (img.clientHeight - natH * scale) / 2
  const sx = Math.max(0, (box.x - offX) / scale)
  const sy = Math.max(0, (box.y - offY) / scale)
  const sw = Math.min(natW - sx, box.w / scale)
  const sh = Math.min(natH - sy, box.h / scale)
  if (sw < 10 || sh < 10) {
    cropBox.value = null
    return
  }
  // canvas 裁出圈选区域，转 JPEG 复用识别接口
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(sw)
  canvas.height = Math.round(sh)
  canvas.getContext('2d').drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
  if (!blob) return
  const uploadBlob = await compressImage(blob) // 裁剪区仍可能偏大，统一压缩后上传

  showLoadingToast({ message: '正在按圈选区域重新识别…', duration: 0, forbidClick: true })
  try {
    const data = await recognizeImage(uploadBlob)
    Object.assign(session, {
      imageDataUrl: URL.createObjectURL(uploadBlob),
      subject: data.subject,
      questionText: data.question_text,
      studentWork: data.student_work,
      hasHandwriting: data.has_handwriting,
      verified: false,
    })
    cropMode.value = false
    cropBox.value = null
    showToast('已按圈选区域重新识别')
  } catch (err) {
    showToast(err.message) // 失败保留圈选模式，方便重圈
  } finally {
    closeToast()
  }
}
</script>

<template>
  <div class="page verify">
    <van-nav-bar title="确认题目" fixed placeholder left-arrow @click-left="router.push('/')" />

    <div class="layout">
      <!-- 原图对照（手机在上 / 桌面在左，3.1 + 3.5）；圈选模式支持手动框住要问的题 -->
      <section class="photo-panel">
        <div class="photo-wrap">
          <img
            ref="imgEl"
            class="photo"
            :class="{ cropping: cropMode }"
            :src="session.imageDataUrl"
            alt="原题照片"
            draggable="false"
            @click="onPhotoClick"
            @pointerdown="onCropDown"
            @pointermove="onCropMove"
            @pointerup="onCropUp"
            @pointercancel="onCropUp"
          />
          <div v-if="cropBox" class="crop-box" :style="boxStyle"></div>
        </div>
        <p class="hint">{{ cropMode ? '在图上拖一个框，框住要问的那道题' : '点击图片可放大核对' }}</p>
        <button class="crop-btn" :class="{ active: cropMode }" @click="toggleCrop">
          {{ cropMode ? '取消圈选' : '识别错了题？圈出要问的题目' }}
        </button>
      </section>

      <!-- 核验表单 -->
      <section class="form-panel">
        <van-notice-bar
          v-if="!session.hasHandwriting"
          wrapable
          :scrollable="false"
          color="#92400E"
          background="#FEF3C7"
        >
          没识别到你的作答，建议补充当时的错误思路，错因分析会更准
        </van-notice-bar>

        <van-cell-group inset class="fields">
          <!-- 学科/年级段：行内胶囊单选，选项少不值得弹层（3.1） -->
          <div class="field-block">
            <p class="field-label">学科</p>
            <div class="chips">
              <button
                v-for="s in subjects"
                :key="s"
                class="chip"
                :class="{ active: session.subject === s }"
                @click="session.subject = s"
              >
                {{ s }}
              </button>
            </div>
          </div>
          <div class="field-block">
            <p class="field-label">年级段</p>
            <div class="chips">
              <button
                v-for="g in grades"
                :key="g"
                class="chip"
                :class="{ active: session.gradeBand === g }"
                @click="session.gradeBand = g"
              >
                {{ g }}
              </button>
            </div>
          </div>
          <van-field
            v-model="session.questionText"
            label="题目原文"
            type="textarea"
            rows="4"
            autosize
            placeholder="题目原文，公式用简记，如 x²/12、√3/2"
          />
          <div v-if="session.questionText" class="katex-preview" v-html="previewHtml"></div>
          <van-field
            v-model="session.studentWork"
            label="我的错误作答"
            type="textarea"
            rows="3"
            autosize
            placeholder="你当时写的演算 / 答案（识别不到可手动补充）"
          />
        </van-cell-group>

        <!-- 两个出口（3.1） -->
        <div class="actions">
          <van-button
            type="primary"
            block
            :disabled="questionTooShort"
            @click="confirm"
          >
            确认无误，开始对话
          </van-button>
          <van-button block plain @click="retake">重新拍一张</van-button>
          <p v-if="questionTooShort" class="warn">题目原文至少 10 个字，才能开始对话</p>
        </div>
      </section>
    </div>

  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 0 32px;
}

.photo-panel {
  padding: 0 16px;
}

.photo {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: #fff;
  cursor: zoom-in;
}

.hint {
  margin: 6px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
}

/* ---- 圈选重识 ---- */
.photo-wrap {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden; /* 圈选暗化遮罩只盖图片区域 */
}

.photo.cropping {
  cursor: crosshair;
  touch-action: none; /* 手机上圈选时禁止页面滚动 */
  user-select: none;
  -webkit-user-select: none;
}

.crop-box {
  position: absolute;
  border: 2px dashed var(--accent);
  background: rgba(245, 158, 11, 0.15);
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.45); /* 框外暗化 */
  border-radius: 4px;
  pointer-events: none;
}

.crop-btn {
  display: block;
  margin: 8px auto 0;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #fff;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.crop-btn.active {
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.fields {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.field-block {
  padding: 10px 16px 4px;
}

.field-block + .field-block,
.field-block + .van-cell {
  border-top: 1px solid var(--border);
}

.field-label {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--text);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 6px;
}

.chip {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}

.chip.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.katex-preview {
  margin: 0 32px 10px;
  padding: 10px 12px;
  min-height: 20px;
  background: var(--bg);
  border: 1px dashed var(--border);
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
  overflow-x: auto;
}

.actions {
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.warn {
  margin: 0;
  text-align: center;
  font-size: 12px;
  color: var(--wrong);
}

/* 桌面端：左右对照（≥768px，3.5） */
@media (min-width: 768px) {
  .layout {
    flex-direction: row;
    align-items: flex-start;
    max-width: 1080px;
    margin: 0 auto;
    padding: 24px 24px 40px;
    gap: 28px;
  }

  .photo-panel {
    flex: 1;
    padding: 0;
    position: sticky;
    top: 60px;
  }

  .photo {
    max-height: 60vh;
  }

  .form-panel {
    flex: 1;
  }
}
</style>
