<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { showImagePreview } from 'vant'
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
</script>

<template>
  <div class="page verify">
    <van-nav-bar title="确认题目" fixed placeholder left-arrow @click-left="router.push('/')" />

    <div class="layout">
      <!-- 原图对照（手机在上 / 桌面在左，3.1 + 3.5） -->
      <section class="photo-panel">
        <img
          class="photo"
          :src="session.imageDataUrl"
          alt="原题照片"
          @click="showImagePreview({ images: [session.imageDataUrl], closeable: true, closeOnPopstate: true, showIndex: false })"
        />
        <p class="hint">点击图片可放大核对</p>
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
