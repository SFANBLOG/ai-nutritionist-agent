<template>
  <div class="min-h-screen bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center py-10">
    <el-card class="w-[440px]" shadow="always">
      <template #header>
        <div class="text-center">
          <h1 class="text-2xl font-bold text-gray-800 m-0">🍎 AI 营养师</h1>
          <p class="text-gray-500 mt-2 mb-0">创建新账户,开启个性化营养管理</p>
        </div>
      </template>

      <el-form ref="formRef" :model="registerForm" :rules="rules" label-width="80px" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="registerForm.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="registerForm.email" placeholder="请输入邮箱" :prefix-icon="Message" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="registerForm.password" type="password" placeholder="至少 6 位" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="registerForm.confirmPassword" type="password" placeholder="再次输入密码" :prefix-icon="Lock" show-password />
        </el-form-item>

        <el-divider content-position="left">
          <span class="text-xs text-gray-400">选填:用于个性化营养计算</span>
        </el-divider>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="年龄" prop="age">
              <el-input-number v-model="registerForm.age" :min="1" :max="120" controls-position="right" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="性别" prop="gender">
              <el-select v-model="registerForm.gender" placeholder="请选择" class="w-full">
                <el-option label="男" value="male" />
                <el-option label="女" value="female" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="身高" prop="height">
              <el-input-number v-model="registerForm.height" :min="80" :max="250" :precision="1" controls-position="right" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="体重" prop="weight">
              <el-input-number v-model="registerForm.weight" :min="20" :max="300" :precision="1" controls-position="right" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" size="large" class="w-full" :loading="loading" @click="handleRegister">
            注册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="text-center text-gray-500 text-sm">
        已有账号?
        <router-link to="/login" class="text-emerald-600 hover:underline">立即登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Message, User } from '@element-plus/icons-vue'
import api from '@/api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  age: 30,
  gender: '',
  height: null,
  weight: null
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次密码输入不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度 2~50 位', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await api.auth.register({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
      age: registerForm.age || null,
      gender: registerForm.gender || null,
      height: registerForm.height || null,
      weight: registerForm.weight || null
    })
    ElMessage.success('注册成功,请登录')
    router.push('/login')
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>
