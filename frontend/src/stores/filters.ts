import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startOfMonth, endOfMonth, subDays, startOfWeek, endOfWeek, subMonths } from 'date-fns'

export type DatePreset = 'today' | 'yesterday' | 'week' | 'month' | 'last_month' | 'custom'
export type CompareMode = 'previous' | 'year_ago' | 'none'

export const useFiltersStore = defineStore('filters', () => {
  // State
  const dateFrom = ref<Date>(startOfMonth(new Date()))
  const dateTo = ref<Date>(new Date())
  const datePreset = ref<DatePreset>('month')
  const compareMode = ref<CompareMode>('previous')

  // Getters
  const dateRange = computed(() => ({
    from: dateFrom.value,
    to: dateTo.value,
  }))

  const dateRangeLabel = computed(() => {
    switch (datePreset.value) {
      case 'today':
        return 'Today'
      case 'yesterday':
        return 'Yesterday'
      case 'week':
        return 'This Week'
      case 'month':
        return 'This Month'
      case 'last_month':
        return 'Last Month'
      default:
        return 'Custom'
    }
  })

  // Actions
  function setDateRange(from: Date, to: Date) {
    dateFrom.value = from
    dateTo.value = to
    datePreset.value = 'custom'
  }

  function setPreset(preset: DatePreset) {
    const today = new Date()
    datePreset.value = preset

    switch (preset) {
      case 'today':
        dateFrom.value = today
        dateTo.value = today
        break
      case 'yesterday':
        dateFrom.value = subDays(today, 1)
        dateTo.value = subDays(today, 1)
        break
      case 'week':
        dateFrom.value = startOfWeek(today, { weekStartsOn: 1 })
        dateTo.value = endOfWeek(today, { weekStartsOn: 1 })
        break
      case 'month':
        dateFrom.value = startOfMonth(today)
        dateTo.value = today
        break
      case 'last_month':
        const lastMonth = subMonths(today, 1)
        dateFrom.value = startOfMonth(lastMonth)
        dateTo.value = endOfMonth(lastMonth)
        break
    }
  }

  function setCompareMode(mode: CompareMode) {
    compareMode.value = mode
  }

  // Initialize with current month
  function reset() {
    setPreset('month')
    compareMode.value = 'previous'
  }

  return {
    // State
    dateFrom,
    dateTo,
    datePreset,
    compareMode,
    // Getters
    dateRange,
    dateRangeLabel,
    // Actions
    setDateRange,
    setPreset,
    setCompareMode,
    reset,
  }
})
