<script setup>
// 设置页（FR-14 / 3.6）：访客自带 Key（BYOK），存本机 localStorage
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { clearKeys, getKeys, saveKeys } from '../store/keys'

const router = useRouter()

const zhipuKey = ref('')
const deepseekKey = ref('')

onMounted(() => {
  const { zhipu = '', deepseek = '' } = getKeys()
  zhipuKey.value = zhipu
  deepseekKey.value = deepseek
})

function save() {
  saveKeys({ zhipu: zhipuKey.value, deepseek: deepseekKey.value })
  showToast('已保存到本机')
}

function clear() {
  clearKeys()
  zhipuKey.value = ''
  deepseekKey.value = ''
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
          这是演示服务，默认使用公共额度。填入你自己的智谱 / DeepSeek
          Key 后，识别和对话都会走你的额度，更快更稳。
        </p>
        <p class="privacy">
          Key 只保存在你设备的浏览器里（localStorage），仅随请求使用，不会被存储到服务器。
          不填也能用。
        </p>
      </div>

      <van-cell-group inset class="fields">
        <van-field
          v-model="zhipuKey"
          label="智谱 Key"
          type="password"
          placeholder="识别图片用（免费申请）"
          clearable
        />
        <van-field
          v-model="deepseekKey"
          label="DeepSeek Key"
          type="password"
          placeholder="对话和笔记用"
          clearable
        />
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

.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
