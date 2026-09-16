<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 m-0">控制台</h2>
        <p class="text-gray-500 text-sm mt-1 mb-0">
          欢迎回来,{{ userStore.displayName }}。AI 营养师已就绪,随时为您生成个性化膳食方案。
        </p>
      </div>
      <el-tag :type="health.llm_configured ? 'success' : 'warning'" effect="dark">
        {{ health.llm_configured ? 'LLM 增强模式' : '规则引擎模式' }}
      </el-tag>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="mb-6">
      <el-col :span="8">
        <el-card shadow="hover" class="cursor-pointer" @click="$router.push('/health-reports')">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-3xl font-bold text-emerald-600">{{ stats.reports }}</div>
              <div class="text-gray-500 text-sm mt-1">健康报告</div>
            </div>
            <div class="text-4xl">📊</div>
          </div>
        </el-card>
      </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="cursor-pointer" @click="$router.push('/recipes')">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-3xl font-bold text-orange-500">{{ stats.recipes }}</div>
                <div class="text-gray-500 text-sm mt-1">个性化食谱</div>
              </div>
              <div class="text-4xl">🍽</div>
            </div>
            <el-tag v-if="stats.pending" type="warning" size="small" class="mt-2">
              {{ stats.pending }} 份待人工确认
            </el-tag>
          </el-card>
        </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="cursor-pointer" @click="$router.push('/preferences')">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-3xl font-bold text-blue-500">{{ stats.preferences }}</div>
              <div class="text-gray-500 text-sm mt-1">口味偏好</div>
            </div>
            <div class="text-4xl">❤</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-card class="mb-6">
      <template #header>
        <span class="font-bold">快捷操作</span>
      </template>
      <div class="flex flex-wrap gap-4">
        <el-button type="primary" size="large" @click="$router.push('/health-reports')">
          📤 上传体检报告
        </el-button>
        <el-button type="success" size="large" @click="$router.push('/recipes')">
          🍎 AI 生成食谱
        </el-button>
        <el-button type="warning" size="large" @click="$router.push('/preferences')">
          ⚙ 设置偏好
        </el-button>
        <el-button size="large" @click="$router.push('/profile')">👤 完善资料</el-button>
      </div>
    </el-card>

    <el-row :gutter="20">
      <!-- Agent 工作流 -->
      <el-col :span="14">
        <el-card class="h-full">
          <template #header>
            <span class="font-bold">LangGraph 多 Agent 协作流程</span>
          </template>
          <div class="flex items-center justify-between flex-wrap gap-2">
            <div
              v-for="(node, i) in agentNodes"
              :key="node.name"
              class="flex items-center"
            >
              <div class="text-center px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 min-w-[110px]">
                <div class="text-xl">{{ node.icon }}</div>
                <div class="text-sm font-medium text-emerald-800">{{ node.name }}</div>
                <div class="text-xs text-gray-500">{{ node.desc }}</div>
              </div>
              <el-icon v-if="i < agentNodes.length - 1" class="mx-1 text-emerald-500">
                <Right />
              </el-icon>
            </div>
          </div>
          <el-alert
            class="mt-4"
            type="info"
            :closable="false"
            show-icon
            title="质量审核环节支持条件回边"
            description="食谱生成 → 质量审核,若审核不通过会自动退回食谱生成 Agent 重做,最多迭代 3 轮。"
          />
        </el-card>
      </el-col>

      <!-- 最近记录 -->
      <el-col :span="10">
        <el-card class="h-full">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-bold">最近动态</span>
            </div>
          </template>
          <el-empty v-if="!recentReports.length && !recentRecipes.length" description="暂无数据,先上传一份体检报告吧" :image-size="80" />
          <div v-else class="space-y-3">
            <div
              v-for="r in recentReports"
              :key="'report-' + r.id"
              class="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-emerald-50 cursor-pointer"
              @click="$router.push(`/health-reports/${r.id}`)"
            >
              <div>
                <div class="text-sm font-medium text-gray-800">📊 {{ r.report_name }}</div>
                <div class="text-xs text-gray-500">{{ formatDate(r.created_at, true) }}</div>
              </div>
              <el-tag size="small" :type="r.analysis_result?.abnormal_count ? 'warning' : 'success'">
                {{ r.analysis_result?.abnormal_count ? r.analysis_result.abnormal_count + ' 项异常' : '指标正常' }}
              </el-tag>
            </div>
            <div
              v-for="r in recentRecipes"
              :key="'recipe-' + r.id"
              class="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-orange-50 cursor-pointer"
              @click="$router.push(`/recipes/${r.id}`)"
            >
              <div>
                <div class="text-sm font-medium text-gray-800">🍽 {{ r.name }}</div>
                <div class="text-xs text-gray-500">{{ formatDate(r.created_at, true) }}</div>
              </div>
              <el-tag size="small" type="warning">{{ r.total_calories }} kcal</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '@/api'
import { useUserStore } from '@/stores/user'
import { formatDate } from '@/utils'

const userStore = useUserStore()

const loading = ref(false)
const stats = reactive({ reports: 0, recipes: 0, preferences: 0, pending: 0 })
const recentReports = ref([])
const recentRecipes = ref([])
const health = ref({ llm_configured: false })

const agentNodes = [
  { name: '健康分析', icon: '🩺', desc: '解读体检指标' },
  { name: '营养规划', icon: '📋', desc: '制定营养方案' },
  { name: '食谱生成', icon: '🍲', desc: '输出三餐食谱' },
  { name: '质量审核', icon: '✅', desc: '校验合理性' }
]

const fetchData = async () => {
  loading.value = true
  try {
    const [reports, recipes, preferences] = await Promise.all([
      api.healthReports.list(),
      api.recipes.list(),
      api.preferences.list()
    ])
    stats.reports = reports.length
    stats.recipes = recipes.length
    stats.preferences = preferences.length
    stats.pending = recipes.filter((r) => r.status === 'pending_review').length
    recentReports.value = reports.slice(0, 3)
    recentRecipes.value = recipes.slice(0, 3)
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }

  try {
    health.value = await api.system.health()
  } catch {
    /* ignore */
  }
}

onMounted(() => {
  fetchData()
  if (!userStore.userInfo) userStore.fetchUserInfo().catch(() => {})
})
</script>
