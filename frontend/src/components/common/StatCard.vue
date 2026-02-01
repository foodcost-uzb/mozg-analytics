<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: string
  loading?: boolean
}>()

const formattedChange = computed(() => {
  if (props.change === undefined) return null
  const sign = props.change >= 0 ? '+' : ''
  return `${sign}${props.change.toFixed(1)}%`
})

const changeColor = computed(() => {
  if (props.change === undefined) return ''
  return props.change >= 0
    ? 'text-success-600 bg-success-50'
    : 'text-danger-600 bg-danger-50'
})
</script>

<template>
  <div class="card p-6">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
          {{ title }}
        </p>
        <div v-if="loading" class="mt-2 h-8 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <p v-else class="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
          {{ value }}
        </p>
        <div v-if="change !== undefined && !loading" class="mt-2 flex items-center">
          <span :class="['inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', changeColor]">
            <svg
              v-if="change >= 0"
              class="w-3 h-3 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
            <svg
              v-else
              class="w-3 h-3 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
            {{ formattedChange }}
          </span>
          <span v-if="changeLabel" class="ml-2 text-xs text-gray-500 dark:text-gray-400">
            {{ changeLabel }}
          </span>
        </div>
      </div>
      <div
        v-if="icon"
        class="p-3 bg-primary-50 dark:bg-primary-900/30 rounded-lg"
      >
        <svg class="w-6 h-6 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="icon" />
        </svg>
      </div>
    </div>
  </div>
</template>
