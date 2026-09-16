import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '控制台' } },
      { path: 'health-reports', name: 'HealthReports', component: () => import('@/views/HealthReports.vue'), meta: { title: '健康报告' } },
      { path: 'health-reports/:id', name: 'HealthReportDetail', component: () => import('@/views/HealthReportDetail.vue'), meta: { title: '报告详情' } },
      { path: 'preferences', name: 'Preferences', component: () => import('@/views/Preferences.vue'), meta: { title: '口味偏好' } },
      { path: 'recipes', name: 'Recipes', component: () => import('@/views/Recipes.vue'), meta: { title: '我的食谱' } },
      { path: 'recipes/:id', name: 'RecipeDetail', component: () => import('@/views/RecipeDetail.vue'), meta: { title: '食谱详情' } },
      { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue'), meta: { title: '个人中心' } }
    ]
  },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { title: '登录' } },
  { path: '/register', name: 'Register', component: () => import('@/views/Register.vue'), meta: { title: '注册' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue'), meta: { title: '404' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫:未登录跳转登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  document.title = to.meta?.title ? `${to.meta.title} | AI 营养师 Agent` : 'AI 营养师 Agent'

  if (!token && !['Login', 'Register'].includes(to.name)) {
    next('/login')
  } else if (token && ['Login', 'Register'].includes(to.name)) {
    next('/')
  } else {
    next()
  }
})

export default router
