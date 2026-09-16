import axios from 'axios'
import { ElMessage } from 'element-plus'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器:注入 JWT
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器:统一解包 data 与错误提示
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail
    let message = '请求失败,请稍后重试'
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail) && detail.length) {
      message = detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    } else if (error.code === 'ECONNABORTED') {
      message = '请求超时,AI 正在思考,请稍后重试'
    } else if (!error.response) {
      message = '无法连接后端服务,请确认后端已在 8000 端口启动'
    }

    ElMessage.error(message)

    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

const api = {
  auth: {
    login: (data) => {
      // OAuth2 密码模式:表单编码
      const form = new URLSearchParams()
      form.append('username', data.username)
      form.append('password', data.password)
      return apiClient.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
    },
    register: (data) => apiClient.post('/auth/register', data),
    me: () => apiClient.get('/users/me')
  },
  users: {
    update: (data) => apiClient.put('/users/me', data)
  },
  healthReports: {
    list: () => apiClient.get('/health-reports/'),
    get: (id) => apiClient.get(`/health-reports/${id}`),
    create: (data) => apiClient.post('/health-reports/', data),
    remove: (id) => apiClient.delete(`/health-reports/${id}`)
  },
  recipes: {
    list: () => apiClient.get('/recipes/'),
    get: (id) => apiClient.get(`/recipes/${id}`),
    menus: (id) => apiClient.get(`/recipes/${id}/menus`),
    generate: (data) => apiClient.post('/recipes/generate', data),
    approveReview: (id, data) => apiClient.post(`/recipes/${id}/review/approve`, data || {}),
    requestRevision: (id, data) => apiClient.post(`/recipes/${id}/review/request-revision`, data),
    remove: (id) => apiClient.delete(`/recipes/${id}`)
  },
  preferences: {
    list: () => apiClient.get('/preferences/'),
    create: (data) => apiClient.post('/preferences/', data),
    remove: (id) => apiClient.delete(`/preferences/${id}`)
  },
  files: {
    upload: (formData) =>
      apiClient.post('/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
  },
  system: {
    health: () => apiClient.get('/health')
  }
}

export default api
