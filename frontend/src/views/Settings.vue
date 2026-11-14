<script setup>
// 设置页（FR-14 / 3.6）：纯 BYOK——识别与对话模型均可自选供应商（智谱/DeepSeek/OpenAI/Claude/Gemini/自定义），
// 全部走 OpenAI 兼容接口；Key 只存本机 localStorage，随请求使用，服务器不落库
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { PROVIDERS, clearKeys, getKeys, modelConfig, saveKeys } from '../store/keys'

const router = useRouter()

// 公共 Key：选智谱/DeepSeek 预设时识别与对话复用这两把
const zhipuKey = ref('')
const deepseekKey = ref('')

// 识别模型 / 对话模型两张卡；model/baseUrl/key 留空表示用预设默认
const recognize = reactive({ provider: 'zhipu', model: '', baseUrl: '', key: '' })
const chat = reactive({ provider: 'deepseek', model: '', baseUrl: '', key: '' })

const recPreset = computed(() => PROVIDERS[recognize.provider] || PROVIDERS.zhipu)
const chatPreset = computed(() => PROVIDERS[chat.provider] || PROVIDERS.deepseek)

onMounted(() => {
  const raw = getKeys()
  zhipuKey.value = raw.zhipu || ''
  deepseekKey.value = raw.deepseek || ''
  const r = modelConfig('recognize')
  const c = modelConfig('chat')
  // 回显：model/baseUrl 与预设默认一致时清空输入框（placeholder 展示默认，语义等价）
  recognize.provider = r.provider
  recognize.model = r.model === recPreset.value.vision ? '' : r.model
  recognize.baseUrl = r.baseUrl === recPreset.value.base ? '' : r.baseUrl
  recognize.key = raw.recognize?.key || ''
  chat.provider = c.provider
  chat.model = c.model === chatPreset.value.chat ? '' : c.model
  chat.baseUrl = c.baseUrl === chatPreset.value.base ? '' : c.baseUrl
  chat.key = raw.chat?.key || ''
})

function save() {
  saveKeys({
    zhipu: zhipuKey.value,
    deepseek: deepseekKey.value,
    recognize: { ...recognize },
    chat: { ...chat },
  })
  showToast('已保存到本机')
}

function clear() {
  clearKeys()
  zhipuKey.value = ''
  deepseekKey.value = ''
  Object.assign(recognize, { provider: 'zhipu', model: '', baseUrl: '', key: '' })
  Object.assign(chat, { provider: 'deepseek', model: '', baseUrl: '', key: '' })
  showToast('已清除本机配置')
}
</script>

<template>
  <div class="page settings">
    <van-nav-bar title="设置" fixed placeholder left-arrow @click-left="router.push('/')" />

    <div class="content">
      <div class="intro">
        <p class="title">为什么要自己配置？</p>
        <p class="desc">
          本服务不内置任何模型 Key——识别和对话用的都是你自己的额度，谁也用不到别人的。
          智谱 Key 在 open.bigmodel.cn 免费申请；也可以接你自己的 DeepSeek / OpenAI / Claude / Gemini，
          或任何 OpenAI 兼容接口（中转站、本地模型都行）。
        </p>
        <p class="privacy">
          Key 与模型配置只保存在你设备的浏览器里（localStorage），仅随请求使用，不会被存储到服务器。
        </p>
      </div>

      <!-- 公共 Key：智谱 / DeepSeek 预设复用这两把 -->
      <p class="section-title">公共 Key</p>
      <van-cell-group inset class="fields">
        <van-field
          v-model="zhipuKey"
          label="智谱 Key"
          type="password"
          placeholder="免费申请（open.bigmodel.cn）"
          clearable
        />
        <van-field
          v-model="deepseekKey"
          label="DeepSeek Key"
          type="password"
          placeholder="platform.deepseek.com 申请"
          clearable
        />
      </van-cell-group>

      <!-- 识别模型卡 -->
      <p class="section-title">识别模型（拍题读题，需支持看图）</p>
      <van-cell-group inset class="fields">
        <van-field label="供应商" readonly>
          <template #input>
            <div class="provider-grid">
              <button
                v-for="(p, key) in PROVIDERS"
                :key="key"
                :class="{ active: recognize.provider === key }"
                @click="recognize.provider = key"
              >
                {{ p.label }}
              </button>
            </div>
          </template>
        </van-field>
        <van-field
          v-model="recognize.model"
          label="模型名"
          :placeholder="recPreset.vision || '如 gpt-4o-mini'"
          clearable
        />
        <van-field
          v-if="recognize.provider === 'custom'"
          v-model="recognize.baseUrl"
          label="接口地址"
          placeholder="OpenAI 兼容 Base URL，如 https://xx.com/v1"
          clearable
        />
        <van-field
          v-if="recPreset.keyFrom === 'self'"
          v-model="recognize.key"
          label="识别 Key"
          type="password"
          placeholder="这把 Key 只用于识别"
          clearable
        />
        <div v-else class="shared-tip">识别将使用上面公共区的{{ recPreset.label }} Key</div>
      </van-cell-group>

      <!-- 对话模型卡 -->
      <p class="section-title">对话模型（错因对话 + 笔记生成）</p>
      <van-cell-group inset class="fields">
        <van-field label="供应商" readonly>
          <template #input>
            <div class="provider-grid">
              <button
                v-for="(p, key) in PROVIDERS"
                :key="key"
                :class="{ active: chat.provider === key }"
                @click="chat.provider = key"
              >
                {{ p.label }}
              </button>
            </div>
          </template>
        </van-field>
        <van-field
          v-model="chat.model"
          label="模型名"
          :placeholder="chatPreset.chat || '如 deepseek-chat'"
          clearable
        />
        <van-field
          v-if="chat.provider === 'custom'"
          v-model="chat.baseUrl"
          label="接口地址"
          placeholder="OpenAI 兼容 Base URL，如 https://xx.com/v1"
          clearable
        />
        <van-field
          v-if="chatPreset.keyFrom === 'self'"
          v-model="chat.key"
          label="对话 Key"
          type="password"
          placeholder="这把 Key 只用于对话与笔记"
          clearable
        />
        <div v-else class="shared-tip">对话将使用上面公共区的{{ chatPreset.label }} Key</div>
      </van-cell-group>

      <div class="actions">
        <van-button type="primary" block @click="save">保存</van-button>
        <van-button block plain @click="clear">清除本机配置</van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.content {
  max-width: 520px;
  margin: 0 auto;
  padding: 20px 0 40px;
}

.intro {
  margin: 0 16px 16px;
  padding: 16px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.intro p {
  margin: 0;
}

.intro .title {
  font-weight: 600;
  margin-bottom: 8px;
}

.intro .desc {
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 8px;
}

.intro .privacy {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.section-title {
  margin: 0 28px 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.fields {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 16px;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  width: 100%;
}

.provider-grid button {
  padding: 6px 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.provider-grid button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.shared-tip {
  padding: 8px 16px 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.actions {
  padding: 4px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
