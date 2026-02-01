<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { format } from 'date-fns'
import { useFiltersStore, useVenuesStore } from '@/stores'
import { reportsApi } from '@/api/reports'
import type { SalesComparison, SalesDataPoint, VenueSales, HourlySales } from '@/types'
import StatCard from '@/components/common/StatCard.vue'
import DataTable from '@/components/common/DataTable.vue'
import LineChart from '@/components/charts/LineChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import PieChart from '@/components/charts/PieChart.vue'

const filtersStore = useFiltersStore()
const venuesStore = useVenuesStore()

// Tabs
type Tab = 'overview' | 'daily' | 'venues' | 'hourly'
const activeTab = ref<Tab>('overview')

// Data state
const loading = ref(false)
const comparison = ref<SalesComparison | null>(null)
const dailySales = ref<SalesDataPoint[]>([])
const venueSales = ref<VenueSales[]>([])
const hourlySales = ref<HourlySales[]>([])

// Format helpers
const formatCurrency = (value: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(value)

const formatNumber = (value: number) =>
  new Intl.NumberFormat('en-US').format(value)

const formatPercent = (value: number) =>
  `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`

// Computed for charts
const dailyChartData = computed(() =>
  dailySales.value.map((d) => ({
    date: format(new Date(d.date), 'MMM d'),
    value: d.revenue,
  }))
)

const venueChartData = computed(() =>
  venueSales.value.map((v) => ({
    name: v.venue_name,
    value: v.revenue,
  }))
)

const hourlyChartData = computed(() =>
  hourlySales.value.map((h) => ({
    label: `${h.hour}:00`,
    value: h.revenue,
  }))
)

// Table columns
const dailyColumns = [
  { key: 'date', label: 'Date', format: (v: string) => format(new Date(v), 'MMM d, yyyy') },
  { key: 'revenue', label: 'Revenue', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'receipts_count', label: 'Receipts', align: 'right' as const, format: (v: number) => formatNumber(v) },
  { key: 'avg_check', label: 'Avg Check', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'guests_count', label: 'Guests', align: 'right' as const, format: (v: number) => formatNumber(v) },
]

const venueColumns = [
  { key: 'venue_name', label: 'Venue' },
  { key: 'revenue', label: 'Revenue', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'revenue_percent', label: '% of Total', align: 'right' as const, format: (v: number) => `${v.toFixed(1)}%` },
  { key: 'receipts_count', label: 'Receipts', align: 'right' as const, format: (v: number) => formatNumber(v) },
  { key: 'avg_check', label: 'Avg Check', align: 'right' as const, format: (v: number) => formatCurrency(v) },
]

// Fetch data
const fetchData = async () => {
  if (venuesStore.selectedVenueIds.length === 0) return

  loading.value = true
  try {
    const venueIds = venuesStore.selectedVenueIds
    const dateFrom = filtersStore.dateFrom
    const dateTo = filtersStore.dateTo

    const [comparisonData, dailyData, venueData, hourlyData] = await Promise.all([
      reportsApi.getSalesComparison(dateFrom, dateTo, 'previous', venueIds),
      reportsApi.getSalesDaily(dateFrom, dateTo, venueIds),
      reportsApi.getSalesByVenue(dateFrom, dateTo, venueIds),
      reportsApi.getSalesHourly(dateFrom, dateTo, venueIds),
    ])

    comparison.value = comparisonData
    dailySales.value = dailyData
    venueSales.value = venueData
    hourlySales.value = hourlyData
  } catch (error) {
    console.error('Failed to fetch sales data:', error)
  } finally {
    loading.value = false
  }
}

// Export to Excel
const handleExport = async () => {
  try {
    const blob = await reportsApi.exportSales(
      filtersStore.dateFrom,
      filtersStore.dateTo,
      venuesStore.selectedVenueIds
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sales_report_${format(filtersStore.dateFrom, 'yyyy-MM-dd')}_${format(filtersStore.dateTo, 'yyyy-MM-dd')}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Export failed:', error)
  }
}

watch(
  () => [filtersStore.dateFrom, filtersStore.dateTo, venuesStore.selectedVenueIds],
  () => fetchData(),
  { deep: true }
)

onMounted(() => {
  if (venuesStore.selectedVenueIds.length > 0) {
    fetchData()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Sales Report</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Detailed sales analysis and trends
        </p>
      </div>
      <button @click="handleExport" class="btn btn-secondary">
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        Export Excel
      </button>
    </div>

    <!-- KPI Cards with comparison -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" v-if="comparison">
      <StatCard
        title="Revenue"
        :value="formatCurrency(comparison.current.revenue)"
        :change="comparison.revenue_diff_percent"
        change-label="vs previous period"
        :loading="loading"
      />
      <StatCard
        title="Receipts"
        :value="formatNumber(comparison.current.receipts_count)"
        :change="comparison.receipts_diff_percent"
        :loading="loading"
      />
      <StatCard
        title="Average Check"
        :value="formatCurrency(comparison.current.avg_check)"
        :change="comparison.avg_check_diff_percent"
        :loading="loading"
      />
      <StatCard
        title="Guests"
        :value="formatNumber(comparison.current.guests_count)"
        :change="comparison.guests_diff_percent"
        :loading="loading"
      />
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 dark:border-gray-700">
      <nav class="flex space-x-8">
        <button
          v-for="tab in [
            { key: 'overview', label: 'Overview' },
            { key: 'daily', label: 'Daily' },
            { key: 'venues', label: 'By Venue' },
            { key: 'hourly', label: 'Hourly' },
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

    <!-- Tab content -->
    <div class="mt-6">
      <!-- Overview -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card p-6">
          <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Revenue Trend</h3>
          <LineChart :data="dailyChartData" :loading="loading" :area-style="true" :value-formatter="formatCurrency" />
        </div>
        <div class="card p-6">
          <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Revenue by Venue</h3>
          <PieChart :data="venueChartData" :loading="loading" :donut="true" :value-formatter="formatCurrency" />
        </div>
      </div>

      <!-- Daily -->
      <div v-if="activeTab === 'daily'" class="card">
        <DataTable :columns="dailyColumns" :data="dailySales" :loading="loading" row-key="date" />
      </div>

      <!-- By Venue -->
      <div v-if="activeTab === 'venues'" class="card">
        <DataTable :columns="venueColumns" :data="venueSales" :loading="loading" row-key="venue_id" />
      </div>

      <!-- Hourly -->
      <div v-if="activeTab === 'hourly'" class="card p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Hourly Revenue</h3>
        <BarChart :data="hourlyChartData" :loading="loading" :value-formatter="formatCurrency" />
      </div>
    </div>
  </div>
</template>
