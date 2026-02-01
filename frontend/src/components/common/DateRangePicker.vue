<script setup lang="ts">
import { ref, computed } from 'vue'
import { format } from 'date-fns'
import type { DatePreset } from '@/stores/filters'

const props = defineProps<{
  dateFrom: Date
  dateTo: Date
  preset: DatePreset
}>()

const emit = defineEmits<{
  'update:date-range': [from: Date, to: Date]
  'update:preset': [preset: DatePreset]
}>()

const showDropdown = ref(false)

const presets: { label: string; value: DatePreset }[] = [
  { label: 'Today', value: 'today' },
  { label: 'Yesterday', value: 'yesterday' },
  { label: 'This Week', value: 'week' },
  { label: 'This Month', value: 'month' },
  { label: 'Last Month', value: 'last_month' },
]

const dateLabel = computed(() => {
  const from = format(props.dateFrom, 'MMM d')
  const to = format(props.dateTo, 'MMM d, yyyy')
  if (from === format(props.dateTo, 'MMM d')) {
    return to
  }
  return `${from} - ${to}`
})

const selectPreset = (preset: DatePreset) => {
  emit('update:preset', preset)
  showDropdown.value = false
}
</script>

<template>
  <div class="relative">
    <button
      @click="showDropdown = !showDropdown"
      class="btn btn-secondary flex items-center space-x-2"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
      <span>{{ dateLabel }}</span>
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown -->
    <div
      v-if="showDropdown"
      class="absolute top-full left-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50"
    >
      <button
        v-for="p in presets"
        :key="p.value"
        @click="selectPreset(p.value)"
        :class="[
          'w-full px-4 py-2 text-left text-sm transition-colors',
          preset === p.value
            ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'
            : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
        ]"
      >
        {{ p.label }}
      </button>
    </div>

    <!-- Click outside to close -->
    <div
      v-if="showDropdown"
      class="fixed inset-0 z-40"
      @click="showDropdown = false"
    />
  </div>
</template>
