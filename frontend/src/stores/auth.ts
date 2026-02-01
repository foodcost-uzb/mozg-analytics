import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { authApi } from '@/api/auth'
import { apiClient } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const userRole = computed(() => user.value?.role ?? null)
  const userName = computed(() => {
    if (!user.value) return ''
    return user.value.last_name
      ? `${user.value.first_name} ${user.value.last_name}`
      : user.value.first_name
  })

  // Check if user has required role
  function hasRole(requiredRoles: string[]): boolean {
    if (!user.value) return false
    return requiredRoles.includes(user.value.role)
  }

  // Initialize auth state from stored tokens
  async function init() {
    if (initialized.value) return

    if (apiClient.hasTokens()) {
      try {
        user.value = await authApi.getCurrentUser()
      } catch {
        apiClient.clearTokens()
      }
    }

    initialized.value = true
  }

  // Login with email/password
  async function login(email: string, password: string) {
    loading.value = true
    error.value = null

    try {
      const tokens = await authApi.login({ email, password })
      apiClient.setTokens(tokens.access_token, tokens.refresh_token)
      user.value = await authApi.getCurrentUser()
    } catch (e: unknown) {
      const axiosError = e as { response?: { data?: { detail?: string } } }
      error.value = axiosError.response?.data?.detail ?? 'Login failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  // Register new organization
  async function register(data: {
    organization_name: string
    organization_slug: string
    email: string
    password: string
    first_name: string
    last_name?: string
  }) {
    loading.value = true
    error.value = null

    try {
      const tokens = await authApi.register(data)
      apiClient.setTokens(tokens.access_token, tokens.refresh_token)
      user.value = await authApi.getCurrentUser()
    } catch (e: unknown) {
      const axiosError = e as { response?: { data?: { detail?: string } } }
      error.value = axiosError.response?.data?.detail ?? 'Registration failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  // Logout
  function logout() {
    user.value = null
    apiClient.clearTokens()
  }

  // Update user data
  function updateUser(updates: Partial<User>) {
    if (user.value) {
      user.value = { ...user.value, ...updates }
    }
  }

  return {
    // State
    user,
    initialized,
    loading,
    error,
    // Getters
    isAuthenticated,
    userRole,
    userName,
    // Actions
    hasRole,
    init,
    login,
    register,
    logout,
    updateUser,
  }
})
