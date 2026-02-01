import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { VenueListItem } from '@/types'
import { venuesApi } from '@/api/venues'

export const useVenuesStore = defineStore('venues', () => {
  // State
  const venues = ref<VenueListItem[]>([])
  const selectedVenueIds = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const activeVenues = computed(() =>
    venues.value.filter((v) => v.is_active)
  )

  const selectedVenues = computed(() =>
    venues.value.filter((v) => selectedVenueIds.value.includes(v.id))
  )

  const allSelected = computed(() =>
    selectedVenueIds.value.length === 0 ||
    selectedVenueIds.value.length === activeVenues.value.length
  )

  // Get venue by ID
  function getVenue(id: string): VenueListItem | undefined {
    return venues.value.find((v) => v.id === id)
  }

  // Fetch all venues
  async function fetchVenues() {
    loading.value = true
    error.value = null

    try {
      venues.value = await venuesApi.list()
      // If no selection, select all active venues
      if (selectedVenueIds.value.length === 0) {
        selectedVenueIds.value = activeVenues.value.map((v) => v.id)
      }
    } catch (e: unknown) {
      const axiosError = e as { response?: { data?: { detail?: string } } }
      error.value = axiosError.response?.data?.detail ?? 'Failed to load venues'
    } finally {
      loading.value = false
    }
  }

  // Select specific venues
  function selectVenues(ids: string[]) {
    selectedVenueIds.value = ids
  }

  // Select all venues
  function selectAll() {
    selectedVenueIds.value = activeVenues.value.map((v) => v.id)
  }

  // Toggle venue selection
  function toggleVenue(id: string) {
    const index = selectedVenueIds.value.indexOf(id)
    if (index === -1) {
      selectedVenueIds.value.push(id)
    } else {
      selectedVenueIds.value.splice(index, 1)
    }
  }

  // Trigger sync for a venue
  async function syncVenue(id: string, fullSync: boolean = false) {
    try {
      await venuesApi.triggerSync(id, fullSync)
      // Refresh venue list to get updated sync status
      await fetchVenues()
    } catch (e: unknown) {
      const axiosError = e as { response?: { data?: { detail?: string } } }
      error.value = axiosError.response?.data?.detail ?? 'Sync failed'
      throw e
    }
  }

  return {
    // State
    venues,
    selectedVenueIds,
    loading,
    error,
    // Getters
    activeVenues,
    selectedVenues,
    allSelected,
    // Actions
    getVenue,
    fetchVenues,
    selectVenues,
    selectAll,
    toggleVenue,
    syncVenue,
  }
})
