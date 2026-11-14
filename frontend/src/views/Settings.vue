<script setup>
// 设置页（FR-14 / 3.6）：纯 BYOK——本服务不内置任何 Key，识别与对话全部使用访客自己的 Key
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { clearKeys, getKeys, saveKeys } from '../store/keys'

const router = useRouter()

const zhipuKey = ref('')
const deepseekKey = ref('')
const chatProvider = ref('deepseek') // deepseek | zhipu

onMounted(() => {
  const { zhipu = '', deepseek = '', chatProvider: provider = 'deepseek' } = getKeys()
  zhipuKey.value = zhipu
  deepseekKey.value = deepseek
  chatProvider.value = provider
})

function save() {
  saveKeys({ zhipu: zhipuKey.value, deepseek: deepseekKey.value, chatProvider: chatProvider.value })
  showToast('已保存到本机')
}

function clear() {
  clearKeys()
  zhipuKey.value = ''
  deepseekKey.value = ''
  chatProvider.value = 'deepseek'
  showToast('已清除本机 Key')
}
</script>

<template>
  <div class="page settings">
    <van-nav-bar title="设置" fixed placeholder left-arrow @click-left="router.push('/')" />

    <div class="content">
      <div class="intro">
        <p class="title">为什么要填 Key？</p>
        <p class="desc">
          本服务不内置任何模型 Key——识别和对话用的都是你自己的额度，谁也用不到别人的。
          智谱 Key 在 open.bigmodel.cn 免费申请，GLM-4-Flash 对话模型同样免费。
        </p>
        <p class="privacy">
          Key 只保存在你设备的浏览器里（localStorage），仅随请求使用，不会被存储到服务器。
        </p>
      </div>

      <van-cell-group inset class="fields">
        <van-field
          v-model="zhipuKey"
          label="智谱 Key"
          type="password"
          placeholder="识别 + 智谱对话共用（免费申请）"
          clearable
        />
        <van-field label="对话模型" readonly>
          <template #input>
            <div class="provider-seg">
              <button :class="{ active: chatProvider === 'deepseek' }" @click="chatProvider = 'deepseek'">
                DeepSeek
              </button>
              <button :class="{ active: chatProvider === 'zhipu' }" @click="chatProvider = 'zhipu'">
                智谱 GLM·免费
              </button>
            </div>
          </template>
        </van-field>
        <van-field
          v-if="chatProvider === 'deepseek'"
          v-model="deepseekKey"
          label="DeepSeek Key"
          type="password"
          placeholder="对话和笔记用（platform.deepseek.com）"
          clearable
        />
        <div v-else class="shared-tip">选智谱 GLM 时，对话与识别共用上面那把智谱 Key</div>
      </van-cell-group>

      <div class="actions">
        <van-button type="primary" block @click="save">保存</van-button>
        <van-button block plain @click="clear">清除本机 Key</van-button>
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

.fields {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.provider-seg {
  display: flex;
  gap: 8px;
  width: 100%;
}

.provider-seg button {
  flex: 1;
  padding: 6px 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.provider-seg button.active {
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
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
