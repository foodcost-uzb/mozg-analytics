<script setup lang="ts">
import type { VenueListItem } from '@/types'

const props = defineProps<{
  venues: VenueListItem[]
  selectedIds: string[]
}>()

const emit = defineEmits<{
  'update:selected-ids': [ids: string[]]
  close: []
}>()

const isSelected = (id: string) => props.selectedIds.includes(id)

const toggleVenue = (id: string) => {
  const newIds = isSelected(id)
    ? props.selectedIds.filter((i) => i !== id)
    : [...props.selectedIds, id]
  emit('update:selected-ids', newIds)
}

const selectAll = () => {
  emit('update:selected-ids', props.venues.map((v) => v.id))
}

const clearAll = () => {
  emit('update:selected-ids', [])
}
</script>

<template>
  <div class="absolute top-full left-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
      <span class="text-sm font-medium text-gray-900 dark:text-white">Select Venues</span>
      <div class="flex space-x-2">
        <button
          @click="selectAll"
          class="text-xs text-primary-600 hover:text-primary-700"
        >
          All
        </button>
        <button
          @click="clearAll"
          class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400"
        >
          Clear
        </button>
      </div>
    </div>

    <!-- Venue list -->
    <div class="max-h-64 overflow-y-auto py-2">
      <label
        v-for="venue in venues"
        :key="venue.id"
        class="flex items-center px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
      >
        <input
          type="checkbox"
          :checked="isSelected(venue.id)"
          @change="toggleVenue(venue.id)"
          class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
        />
        <span class="ml-3 text-sm text-gray-700 dark:text-gray-300">
          {{ venue.name }}
        </span>
      </label>
    </div>

    <!-- Footer -->
    <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
      <button
        @click="emit('close')"
        class="w-full btn btn-primary text-sm"
      >
        Apply
      </button>
    </div>
  </div>

  <!-- Click outside to close -->
  <div
    class="fixed inset-0 z-40"
    @click="emit('close')"
  />
</template>
