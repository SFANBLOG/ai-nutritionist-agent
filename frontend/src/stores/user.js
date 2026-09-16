import { defineStore } from 'pinia'
import api from '@/api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    userInfo: null
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    displayName: (state) => state.userInfo?.full_name || state.userInfo?.username || '用户',
    bmi: (state) => state.userInfo?.bmi ?? null
  },

  actions: {
    async login(credentials) {
      const data = await api.auth.login(credentials)
      this.token = data.access_token
      localStorage.setItem('token', this.token)
      await this.fetchUserInfo()
    },

    async fetchUserInfo() {
      if (!this.token) return null
      this.userInfo = await api.auth.me()
      return this.userInfo
    },

    async updateProfile(payload) {
      this.userInfo = await api.users.update(payload)
      return this.userInfo
    },

    logout() {
      this.token = ''
      this.userInfo = null
      localStorage.removeItem('token')
    }
  }
})
