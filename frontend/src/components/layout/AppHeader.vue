<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useVenuesStore } from '@/stores/venues'
import { useFiltersStore } from '@/stores/filters'
import DateRangePicker from '@/components/common/DateRangePicker.vue'
import VenueSelector from '@/components/common/VenueSelector.vue'

const venuesStore = useVenuesStore()
const filtersStore = useFiltersStore()

const showVenueSelector = ref(false)

onMounted(async () => {
  await venuesStore.fetchVenues()
})
</script>

<template>
  <header class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center px-6">
    <div class="flex-1 flex items-center space-x-4">
      <!-- Date Range Picker -->
      <DateRangePicker
        :date-from="filtersStore.dateFrom"
        :date-to="filtersStore.dateTo"
        :preset="filtersStore.datePreset"
        @update:date-range="filtersStore.setDateRange"
        @update:preset="filtersStore.setPreset"
      />

      <!-- Venue Selector -->
      <div class="relative">
        <button
          @click="showVenueSelector = !showVenueSelector"
          class="btn btn-secondary flex items-center space-x-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <span>
            {{ venuesStore.allSelected ? 'All Venues' : `${venuesStore.selectedVenueIds.length} Venues` }}
          </span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <VenueSelector
          v-if="showVenueSelector"
          :venues="venuesStore.activeVenues"
          :selected-ids="venuesStore.selectedVenueIds"
          @update:selected-ids="venuesStore.selectVenues"
          @close="showVenueSelector = false"
        />
      </div>
    </div>

    <!-- Right side actions -->
    <div class="flex items-center space-x-4">
      <!-- Refresh button -->
      <button
        class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
        title="Refresh data"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>
  </header>
</template>
