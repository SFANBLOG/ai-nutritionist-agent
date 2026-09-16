<template>
  <el-container class="min-h-screen">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="bg-gradient-to-b from-emerald-700 to-emerald-900 text-white">
      <div class="p-6 text-center border-b border-emerald-600">
        <h1 class="text-xl font-bold m-0">🍎 AI 营养师</h1>
        <p class="text-emerald-200 text-sm mt-1 mb-0">智能饮食管理</p>
      </div>

      <el-menu :default-active="activeMenu" router class="sidebar-menu mt-2">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>

      <!-- Agent 状态 -->
      <div class="px-4 mt-6">
        <div class="bg-emerald-800/60 rounded-lg p-3 text-xs">
          <div class="flex items-center gap-2 mb-1">
            <span class="w-2 h-2 rounded-full" :class="health.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'"></span>
            <span class="font-semibold">Agent 运行状态</span>
          </div>
          <div class="text-emerald-200 leading-5">
            <div>LLM:{{ health.llm_configured ? '已启用' : '规则引擎模式' }}</div>
            <div>知识库:{{ health.knowledge_backend || '-' }}</div>
            <div>知识条目:{{ health.knowledge_docs ?? '-' }}</div>
          </div>
        </div>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <el-header class="bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div class="text-gray-700 font-medium">{{ route.meta?.title || '' }}</div>
        <div class="flex items-center gap-4">
          <el-tag v-if="userStore.bmi" type="success" effect="plain" size="small">
            BMI {{ userStore.bmi }}
          </el-tag>
          <el-dropdown @command="handleCommand">
            <span class="flex items-center gap-2 cursor-pointer text-gray-700">
              <el-avatar :size="30" class="bg-emerald-600">
                {{ userStore.displayName.slice(0, 1) }}
              </el-avatar>
              {{ userStore.displayName }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="bg-gray-50 p-6">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menus = [
  { path: '/', label: '控制台', icon: 'HomeFilled' },
  { path: '/health-reports', label: '健康报告', icon: 'Document' },
  { path: '/recipes', label: '我的食谱', icon: 'Bowl' },
  { path: '/preferences', label: '口味偏好', icon: 'Setting' }
]

const activeMenu = computed(() => {
  if (route.path.startsWith('/health-reports')) return '/health-reports'
  if (route.path.startsWith('/recipes')) return '/recipes'
  if (route.path.startsWith('/preferences')) return '/preferences'
  if (route.path.startsWith('/profile')) return ''
  return '/'
})

const health = ref({ status: 'unknown', llm_configured: false, knowledge_backend: '', knowledge_docs: 0 })

const fetchHealth = async () => {
  try {
    health.value = await api.system.health()
  } catch {
    health.value = { status: 'down', llm_configured: false, knowledge_backend: '-', knowledge_docs: '-' }
  }
}

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo().catch(() => {})
  }
  fetchHealth()
})
</script>
