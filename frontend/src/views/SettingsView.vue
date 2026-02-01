<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useVenuesStore } from '@/stores/venues'
import { useAuthStore } from '@/stores/auth'
import type { Venue, VenueListItem } from '@/types'
import { venuesApi } from '@/api/venues'

const venuesStore = useVenuesStore()
const authStore = useAuthStore()

// Tabs
type Tab = 'venues' | 'account'
const activeTab = ref<Tab>('venues')

// State
const loading = ref(false)
const syncingVenue = ref<string | null>(null)

// Sync venue data
const handleSync = async (venueId: string, fullSync: boolean = false) => {
  syncingVenue.value = venueId
  try {
    await venuesStore.syncVenue(venueId, fullSync)
  } finally {
    syncingVenue.value = null
  }
}

// Format date
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleString()
}

// Get status color
const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'bg-success-100 text-success-800'
    case 'in_progress':
      return 'bg-primary-100 text-primary-800'
    case 'failed':
      return 'bg-danger-100 text-danger-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

onMounted(async () => {
  await venuesStore.fetchVenues()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Settings</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Manage venues, sync settings, and account
      </p>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 dark:border-gray-700">
      <nav class="flex space-x-8">
        <button
          v-for="tab in [
            { key: 'venues', label: 'Venues' },
            { key: 'account', label: 'Account' },
          ]"
          :key="tab.key"
          @click="activeTab = tab.key as Tab"
          :class="[
            'py-4 px-1 border-b-2 font-medium text-sm',
            activeTab === tab.key
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          ]"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- Venues tab -->
    <div v-if="activeTab === 'venues'" class="space-y-4">
      <div
        v-for="venue in venuesStore.venues"
        :key="venue.id"
        class="card p-6"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-3">
              <h3 class="text-lg font-medium text-gray-900 dark:text-white">
                {{ venue.name }}
              </h3>
              <span
                :class="[
                  'px-2 py-1 text-xs font-medium rounded-full',
                  venue.is_active ? 'bg-success-100 text-success-800' : 'bg-gray-100 text-gray-600'
                ]"
              >
                {{ venue.is_active ? 'Active' : 'Inactive' }}
              </span>
              <span
                :class="[
                  'px-2 py-1 text-xs font-medium rounded-full uppercase',
                  getStatusColor(venue.sync_status)
                ]"
              >
                {{ venue.sync_status }}
              </span>
            </div>

            <div class="mt-2 text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <p v-if="venue.address">{{ venue.address }}, {{ venue.city }}</p>
              <p>POS: {{ venue.pos_type.toUpperCase() }}</p>
              <p>Last sync: {{ formatDate(venue.last_sync_at) }}</p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <button
              @click="handleSync(venue.id, false)"
              :disabled="syncingVenue === venue.id"
              class="btn btn-secondary text-sm"
            >
              <svg
                v-if="syncingVenue === venue.id"
                class="animate-spin -ml-1 mr-2 h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <svg v-else class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Quick Sync
            </button>
            <button
              @click="handleSync(venue.id, true)"
              :disabled="syncingVenue === venue.id"
              class="btn btn-primary text-sm"
            >
              Full Sync
            </button>
          </div>
        </div>
      </div>

      <div v-if="venuesStore.venues.length === 0 && !venuesStore.loading" class="card p-8 text-center">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">No venues</h3>
        <p class="mt-1 text-sm text-gray-500">Get started by adding a new venue.</p>
      </div>
    </div>

    <!-- Account tab -->
    <div v-if="activeTab === 'account'" class="card p-6 max-w-2xl">
      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-6">Account Information</h3>

      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">First Name</label>
            <input type="text" :value="authStore.user?.first_name" disabled class="input bg-gray-50" />
          </div>
          <div>
            <label class="label">Last Name</label>
            <input type="text" :value="authStore.user?.last_name || '-'" disabled class="input bg-gray-50" />
          </div>
        </div>

        <div>
          <label class="label">Email</label>
          <input type="email" :value="authStore.user?.email || '-'" disabled class="input bg-gray-50" />
        </div>

        <div>
          <label class="label">Role</label>
          <input type="text" :value="authStore.user?.role" disabled class="input bg-gray-50 capitalize" />
        </div>

        <div v-if="authStore.user?.telegram_username">
          <label class="label">Telegram</label>
          <input type="text" :value="'@' + authStore.user?.telegram_username" disabled class="input bg-gray-50" />
        </div>
      </div>
    </div>
  </div>
</template>
