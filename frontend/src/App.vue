<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'

const route = useRoute()
const authStore = useAuthStore()

const isAuthPage = computed(() => route.meta.requiresAuth === false)
const isAuthenticated = computed(() => authStore.isAuthenticated)
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Auth pages (login, register) -->
    <template v-if="isAuthPage">
      <router-view />
    </template>

    <!-- Main app layout -->
    <template v-else-if="isAuthenticated">
      <div class="flex h-screen overflow-hidden">
        <!-- Sidebar -->
        <AppSidebar />

        <!-- Main content -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <!-- Header -->
          <AppHeader />

          <!-- Page content -->
          <main class="flex-1 overflow-y-auto p-6">
            <router-view />
          </main>
        </div>
      </div>
    </template>

    <!-- Loading state -->
    <template v-else>
      <div class="flex items-center justify-center h-screen">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    </template>
  </div>
</template>
