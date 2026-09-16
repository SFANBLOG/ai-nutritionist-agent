<template>
  <div class="min-h-screen bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center">
    <el-card class="w-[400px]" shadow="always">
      <template #header>
        <div class="text-center">
          <h1 class="text-2xl font-bold text-gray-800 m-0">🍎 AI 营养师</h1>
          <p class="text-gray-500 mt-2 mb-0">登录您的账户</p>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="rules"
        size="large"
        autocomplete="off"
        @submit.prevent
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            name="username"
            autocomplete="username"
            placeholder="用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            ref="passwordRef"
            v-model="loginForm.password"
            name="password"
            autocomplete="new-password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" class="w-full" :loading="loading" @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="text-center text-gray-500 text-sm">
        还没有账号?
        <router-link to="/register" class="text-emerald-600 hover:underline">立即注册</router-link>
      </div>

      <el-alert
        class="mt-4"
        type="info"
        :closable="false"
        show-icon
        title="默认测试账号"
        description="用户名 admin / 密码 admin123"
      />
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const passwordRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username.trim(),
      password: loginForm.password
    })
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // 错误提示已由拦截器统一处理。
    // 登录失败时清空密码框:避免浏览器自动填充的旧密码被反复提交,
    // 造成「输对了却一直提示用户名或密码错误」的假象。
    loginForm.password = ''
    passwordRef.value?.focus?.()
  } finally {
    loading.value = false
  }
}
</script>
