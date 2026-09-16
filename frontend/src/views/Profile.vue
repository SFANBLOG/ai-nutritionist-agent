<template>
  <div>
    <h2 class="text-2xl font-bold text-gray-800 mb-6 m-0">个人中心</h2>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span class="font-bold">基础资料</span>
          </template>
          <el-form :model="form" label-width="100px" v-loading="loading">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="用户名">
                  <el-input :model-value="userStore.userInfo?.username" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="邮箱">
                  <el-input :model-value="userStore.userInfo?.email" disabled />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="真实姓名">
                  <el-input v-model="form.full_name" placeholder="请输入真实姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="手机号">
                  <el-input v-model="form.phone" placeholder="请输入手机号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="年龄">
                  <el-input-number v-model="form.age" :min="1" :max="120" controls-position="right" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="性别">
                  <el-select v-model="form.gender" placeholder="请选择" class="w-full">
                    <el-option label="男" value="male" />
                    <el-option label="女" value="female" />
                    <el-option label="其他" value="other" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="BMI">
                  <el-input :model-value="userStore.bmi ?? '-'" disabled />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="身高 (cm)">
                  <el-input-number v-model="form.height" :min="80" :max="250" :precision="1" controls-position="right" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="体重 (kg)">
                  <el-input-number v-model="form.weight" :min="20" :max="300" :precision="1" controls-position="right" class="w-full" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider content-position="left">
              <span class="text-xs text-gray-400">修改密码(留空则不修改)</span>
            </el-divider>
            <el-form-item label="新密码">
              <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="mb-5 text-center">
          <el-avatar :size="80" class="bg-emerald-600 text-2xl">
            {{ userStore.displayName.slice(0, 1) }}
          </el-avatar>
          <div class="text-lg font-bold text-gray-800 mt-3">{{ userStore.displayName }}</div>
          <div class="text-sm text-gray-500">{{ userStore.userInfo?.email }}</div>
          <el-divider />
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="bg-gray-50 rounded p-3">
              <div class="text-gray-500">BMI</div>
              <div class="font-bold text-emerald-600">{{ userStore.bmi ?? '-' }}</div>
            </div>
            <div class="bg-gray-50 rounded p-3">
              <div class="text-gray-500">基础代谢参考</div>
              <div class="font-bold text-orange-500">{{ bmr }}</div>
            </div>
          </div>
          <div class="text-xs text-gray-400 mt-3">
            完善身高体重后,AI 可更准确地计算每日热量目标
          </div>
        </el-card>

        <el-card>
          <template #header>
            <span class="font-bold">数据概览</span>
          </template>
          <div class="space-y-2 text-sm">
            <div class="flex justify-between"><span class="text-gray-500">健康报告</span><span>{{ counts.reports }}</span></div>
            <div class="flex justify-between"><span class="text-gray-500">个性化食谱</span><span>{{ counts.recipes }}</span></div>
            <div class="flex justify-between"><span class="text-gray-500">口味偏好</span><span>{{ counts.preferences }}</span></div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const saving = ref(false)
const counts = reactive({ reports: 0, recipes: 0, preferences: 0 })

const form = reactive({
  full_name: '',
  phone: '',
  age: null,
  gender: '',
  height: null,
  weight: null,
  password: ''
})

const bmr = computed(() => {
  const u = userStore.userInfo
  if (!u?.height || !u?.weight || !u?.age) return '-'
  const base = 10 * u.weight + 6.25 * u.height - 5 * u.age
  const value = u.gender === 'male' ? base + 5 : base - 161
  return `${Math.round(value)} kcal`
})

const resetForm = () => {
  const u = userStore.userInfo || {}
  form.full_name = u.full_name || ''
  form.phone = u.phone || ''
  form.age = u.age ?? null
  form.gender = u.gender || ''
  form.height = u.height ?? null
  form.weight = u.weight ?? null
  form.password = ''
}

const handleSave = async () => {
  saving.value = true
  try {
    const payload = {
      full_name: form.full_name || null,
      phone: form.phone || null,
      age: form.age || null,
      gender: form.gender || null,
      height: form.height || null,
      weight: form.weight || null
    }
    if (form.password) payload.password = form.password
    await userStore.updateProfile(payload)
    ElMessage.success('资料已更新')
    form.password = ''
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

const fetchCounts = async () => {
  try {
    const [reports, recipes, preferences] = await Promise.all([
      api.healthReports.list(),
      api.recipes.list(),
      api.preferences.list()
    ])
    counts.reports = reports.length
    counts.recipes = recipes.length
    counts.preferences = preferences.length
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  loading.value = true
  try {
    if (!userStore.userInfo) await userStore.fetchUserInfo()
    resetForm()
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
  fetchCounts()
})
</script>
