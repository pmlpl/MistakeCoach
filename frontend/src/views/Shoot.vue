<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { recognizeImage } from '../api'
import { getKeys } from '../store/keys'
import { loadDraft } from '../store/chat'
import { session } from '../store/session'

const router = useRouter()

const cameraInput = ref(null)
const albumInput = ref(null)
const desktopInput = ref(null)
const dragging = ref(false)
const loading = ref(false)
const previewUrl = ref('')

// 未配 Key 引导（3.6 纯 BYOK）：识别必须有智谱 Key
const needKey = ref(false)

// 草稿续聊入口（FR-12）：有未完成对话时拍题页显示横幅
const hasDraft = ref(false)
const draftPreview = ref('')

onMounted(() => {
  window.addEventListener('paste', onPaste)
  needKey.value = !getKeys().zhipu
  const d = loadDraft()
  if (d?.question?.questionText) {
    hasDraft.value = true
    draftPreview.value = d.question.questionText.slice(0, 40)
  }
})
onUnmounted(() => window.removeEventListener('paste', onPaste))

function pick(type) {
  const map = { camera: cameraInput, album: albumInput, desktop: desktopInput }
  map[type].value.click()
}

function onPickFile(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // 允许重复选择同一文件
  if (file) recognize(file)
}

function onDrop(e) {
  dragging.value = false
  const file = [...(e.dataTransfer?.files || [])].find((f) => f.type.startsWith('image/'))
  if (file) recognize(file)
  else showToast('请拖入图片文件')
}

// 桌面端 Ctrl+V 粘贴（3.5 三通道之一）
function onPaste(e) {
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'))
  const file = item?.getAsFile()
  if (file) recognize(file)
}

async function recognize(file) {
  if (loading.value) return
  previewUrl.value = URL.createObjectURL(file)
  loading.value = true
  showLoadingToast({ message: 'AI 正在识别题目…', duration: 0, forbidClick: true })
  try {
    const data = await recognizeImage(file)
    Object.assign(session, {
      imageDataUrl: previewUrl.value,
      subject: data.subject,
      questionText: data.question_text,
      studentWork: data.student_work,
      hasHandwriting: data.has_handwriting,
      verified: false,
    })
    router.push('/verify')
  } catch (err) {
    previewUrl.value = '' // 失败回到选择入口，允许换一张
    showToast(err.message)
  } finally {
    loading.value = false
    closeToast()
  }
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
        <span class="key-title">先配置模型 Key</span>
        <span class="key-desc">识别用智谱 Key（免费申请），到设置页粘贴即可</span>
        <van-icon name="setting-o" />
      </button>

      <!-- 继续上次对话（FR-12 草稿续聊入口，M3 并入错题本） -->
      <button v-if="hasDraft && !previewUrl" class="draft-banner" @click="router.push('/chat')">
        <span class="draft-title">继续上次对话</span>
        <span class="draft-preview">{{ draftPreview }}</span>
        <van-icon name="arrow" />
      </button>

      <template v-if="previewUrl">
        <!-- 识别中预览 -->
        <div class="preview">
          <img :src="previewUrl" alt="题目照片" />
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

.preview img {
  display: block;
  width: 100%;
  border-radius: var(--radius);
  border: 1px solid var(--border);
}
</style>
