<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { recognizeImage } from '../api'
import { compressImage } from '../utils/image'
import { modelConfig } from '../store/keys'
import { latestDraft, newSessionId } from '../store/chat'
import { session } from '../store/session'

const router = useRouter()

const cameraInput = ref(null)
const albumInput = ref(null)
const desktopInput = ref(null)
const dragging = ref(false)
const loading = ref(false)
const previewUrl = ref('')
const previewBlob = ref(null) // 待识别图（已压缩，可能已被圈选裁剪）

// 未配 Key 引导（3.6 纯 BYOK）：识别按设置页所选模型检查对应 Key 是否就绪
const needKey = ref(false)

// 草稿续聊入口（FR-12）：有未完成对话时拍题页显示横幅，指向最近更新的会话桶
const hasDraft = ref(false)
const draftPreview = ref('')
const draftSid = ref('')

onMounted(() => {
  window.addEventListener('paste', onPaste)
  needKey.value = !modelConfig('recognize').key
  const d = latestDraft()
  if (d?.question?.questionText) {
    hasDraft.value = true
    draftPreview.value = d.question.questionText.slice(0, 40)
    draftSid.value = d.sid
  }
})
onUnmounted(() => window.removeEventListener('paste', onPaste))

// 继续上次对话：带会话桶 id 进入，恢复对应题的对话（多个桶时横幅指向最近更新的）
function goDraft() {
  router.push({ name: 'chat', query: { sid: draftSid.value } })
}

function pick(type) {
  const map = { camera: cameraInput, album: albumInput, desktop: desktopInput }
  map[type].value.click()
}

function onPickFile(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // 允许重复选择同一文件
  if (file) prepare(file)
}

function onDrop(e) {
  dragging.value = false
  const file = [...(e.dataTransfer?.files || [])].find((f) => f.type.startsWith('image/'))
  if (file) prepare(file)
  else showToast('请拖入图片文件')
}

// 桌面端 Ctrl+V 粘贴（3.5 三通道之一）
function onPaste(e) {
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'))
  const file = item?.getAsFile()
  if (file) prepare(file)
}

// 选图后先进预览态：可先圈出题目，再手动点识别（圈选在识别之前完成）
async function prepare(file) {
  try {
    const blob = await compressImage(file) // 压缩后再上传：识别更快，防免费模型超时
    previewUrl.value = URL.createObjectURL(blob)
    previewBlob.value = blob
    cropMode.value = false
    cropBox.value = null
  } catch (err) {
    showToast(err.message)
  }
}

function clearPreview() {
  URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  previewBlob.value = null
  cropMode.value = false
  cropBox.value = null
}

async function startRecognize() {
  if (!previewBlob.value || loading.value) return
  loading.value = true
  showLoadingToast({ message: 'AI 正在识别题目…', duration: 0, forbidClick: true })
  try {
    const data = await recognizeImage(previewBlob.value)
    Object.assign(session, {
      imageDataUrl: previewUrl.value,
      sessionId: newSessionId(), // 拍新题 = 新会话桶 id，绝不覆盖其他题的对话
      subject: data.subject,
      questionText: data.question_text,
      studentWork: data.student_work,
      hasHandwriting: data.has_handwriting,
      verified: false,
    })
    router.push('/verify')
  } catch (err) {
    showToast({ message: `识别失败：${err.message}`, duration: 5000 }) // 保留预览便于重试
  } finally {
    loading.value = false
    closeToast()
  }
}

// ---- 圈选题目：拖框框住要问的题，松手即裁剪替换预览 ----
const imgEl = ref(null)
const cropMode = ref(false)
const cropping = ref(false)
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

function onCropUp() {
  if (!cropping.value) return
  cropping.value = false
  const b = cropBox.value
  if (!b || b.w < 40 || b.h < 40) {
    cropBox.value = null // 太小视为误触
  }
  // 选好的框保留不动，等用户点「确认裁剪」才生效；不满意可直接重新拖框覆盖
}

function confirmCrop() {
  const b = cropBox.value
  if (!b) return
  const img = imgEl.value
  const natW = img.naturalWidth
  const natH = img.naturalHeight
  // object-fit: contain：显示框与实际绘制区存在留白偏移，先映射回原图像素坐标
  const scale = Math.min(img.clientWidth / natW, img.clientHeight / natH)
  const offX = (img.clientWidth - natW * scale) / 2
  const offY = (img.clientHeight - natH * scale) / 2
  const sx = Math.max(0, (b.x - offX) / scale)
  const sy = Math.max(0, (b.y - offY) / scale)
  const sw = Math.min(natW - sx, b.w / scale)
  const sh = Math.min(natH - sy, b.h / scale)
  if (sw < 10 || sh < 10) {
    cropBox.value = null
    return
  }
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(sw)
  canvas.height = Math.round(sh)
  canvas.getContext('2d').drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => {
    if (!blob) return
    URL.revokeObjectURL(previewUrl.value)
    previewBlob.value = blob
    previewUrl.value = URL.createObjectURL(blob)
    cropMode.value = false
    cropBox.value = null
    showToast('已按圈选裁剪，可直接开始识别')
  }, 'image/jpeg', 0.92)
}
</script>

<template>
  <div class="page shoot">
    <van-nav-bar title="拍题" fixed placeholder>
      <template #right>
        <div class="nav-actions">
          <!-- 错题本、设置入口 = 拍题页顶栏图标（3.4） -->
          <van-icon name="apps-o" size="22" @click="router.push('/book')" />
          <van-icon name="setting-o" size="22" @click="router.push('/settings')" />
        </div>
      </template>
    </van-nav-bar>

    <main class="content">
      <!-- 未配 Key 引导（3.6 纯 BYOK） -->
      <button v-if="needKey && !previewUrl" class="key-banner" @click="router.push('/settings')">
        <span class="key-title">先配置识别模型</span>
        <span class="key-desc">支持智谱（免费）/ DeepSeek / GPT / Claude 等，到设置页粘贴 Key 即可</span>
        <van-icon name="setting-o" />
      </button>

      <!-- 继续上次对话（FR-12 草稿续聊入口）：按 sessionId 恢复最近未完成会话 -->
      <button v-if="hasDraft && !previewUrl" class="draft-banner" @click="goDraft">
        <span class="draft-title">继续上次对话</span>
        <span class="draft-preview">{{ draftPreview }}</span>
        <van-icon name="arrow" />
      </button>

      <template v-if="previewUrl">
        <!-- 识别前预览：可先圈出题目，再手动开始识别 -->
        <div class="preview">
          <div class="photo-wrap">
            <img
              ref="imgEl"
              :src="previewUrl"
              alt="题目照片"
              :class="{ cropping: cropMode }"
              draggable="false"
              @pointerdown="onCropDown"
              @pointermove="onCropMove"
              @pointerup="onCropUp"
              @pointercancel="onCropUp"
            />
            <div v-if="cropBox" class="crop-box" :style="boxStyle"></div>
          </div>
          <p class="preview-hint">
            {{
              cropMode
                ? cropBox && !cropping
                  ? '满意就点「确认裁剪」，不满意直接重新拖框'
                  : '在图上拖一个框，框住要问的那道题'
                : '可以先圈出题目，也可以直接开始识别'
            }}
          </p>
          <div class="preview-actions">
            <template v-if="cropMode && cropBox && !cropping">
              <!-- 框已选好，等确认 -->
              <button class="big-btn" @click="confirmCrop">确认裁剪</button>
              <button class="big-btn secondary" @click="cropBox = null">重新框选</button>
            </template>
            <template v-else>
              <button class="big-btn" :disabled="loading" @click="startRecognize">开始识别</button>
              <button class="big-btn secondary" @click="toggleCrop">{{ cropMode ? '取消圈选' : '圈出题目' }}</button>
              <button class="text-btn" @click="clearPreview">重选一张</button>
            </template>
          </div>
        </div>
      </template>

      <template v-else>
        <!-- 手机端：拍照 / 相册（<768px，3.5） -->
        <div class="mobile-actions">
          <button class="big-btn" @click="pick('camera')">拍照</button>
          <button class="big-btn secondary" @click="pick('album')">从相册选</button>
        </div>

        <!-- 桌面端：拖入 / 点选 / 粘贴三通道（≥768px） -->
        <div class="desktop-entry">
          <div
            class="dropzone"
            :class="{ dragging }"
            @click="pick('desktop')"
            @dragover.prevent="dragging = true"
            @dragleave="dragging = false"
            @drop.prevent="onDrop"
          >
            <van-icon name="photograph" size="40" />
            <p>把错题照片拖到这里、点击选择，或 Ctrl+V 粘贴</p>
            <span class="tip">记得连同你当时的错误作答一起拍进去</span>
          </div>
          <ol class="steps">
            <li>拍下或上传错题（连同你的错误作答）</li>
            <li>确认 AI 识别的题目内容</li>
            <li>和 AI 对话找到错因，生成错题卡</li>
          </ol>
        </div>
      </template>

      <input
        ref="cameraInput"
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        @change="onPickFile"
      />
      <input ref="albumInput" type="file" accept="image/*" hidden @change="onPickFile" />
      <input ref="desktopInput" type="file" accept="image/*" hidden @change="onPickFile" />
    </main>
  </div>
</template>

<style scoped>
.nav-actions {
  display: flex;
  align-items: center;
  gap: 18px;
}

.content {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px 16px 40px;
}

.key-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 18px;
  padding: 12px 14px;
  background: #fef3c7;
  border: 1.5px solid var(--accent);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
}

.key-title {
  font-size: 14px;
  font-weight: 600;
  color: #92400e;
  white-space: nowrap;
}

.key-desc {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
}

.draft-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 18px;
  padding: 14px 16px;
  background: #fff;
  border: 1.5px solid var(--accent);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
}

.draft-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}

.draft-preview {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 两端入口切换 */
.mobile-actions {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 12vh;
}

.desktop-entry {
  display: none;
}

@media (min-width: 768px) {
  .mobile-actions {
    display: none;
  }

  .desktop-entry {
    display: block;
  }
}

.big-btn {
  height: 56px;
  border: none;
  border-radius: var(--radius);
  background: var(--accent);
  color: #fff;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.09s ease-out;
}

.big-btn:active {
  transform: scale(0.955);
}

.big-btn.secondary {
  background: #fff;
  color: var(--accent);
  border: 1.5px solid var(--accent);
}

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 64px 24px;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  background: #fff;
  cursor: pointer;
  color: var(--text-secondary);
  transition: border-color 0.12s, background 0.12s;
}

.dropzone.dragging {
  border-color: var(--accent);
  background: #fef6e0;
}

.dropzone p {
  margin: 0;
  font-size: 15px;
}

.dropzone .tip {
  font-size: 13px;
  opacity: 0.8;
}

.steps {
  margin: 20px 0 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.9;
}

/* 识别前预览 + 圈选 */
.preview img {
  display: block;
  width: 100%;
  max-height: 50vh;
  object-fit: contain;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: #fff;
}

.photo-wrap {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden; /* 圈选暗化遮罩只盖图片区域 */
}

.preview img.cropping {
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

.preview-hint {
  margin: 8px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.preview-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.preview-actions .big-btn {
  width: 100%;
}

.text-btn {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-decoration: underline;
  padding: 4px;
}
</style>
