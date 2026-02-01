<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { format } from 'date-fns'
import { useFiltersStore, useVenuesStore } from '@/stores'
import { reportsApi } from '@/api/reports'
import type { SalesSummary, SalesDataPoint, HourlySales, ProductMargin } from '@/types'
import StatCard from '@/components/common/StatCard.vue'
import LineChart from '@/components/charts/LineChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import HeatmapChart from '@/components/charts/HeatmapChart.vue'

const filtersStore = useFiltersStore()
const venuesStore = useVenuesStore()

// Data state
const loading = ref(false)
const summary = ref<SalesSummary | null>(null)
const previousSummary = ref<SalesSummary | null>(null)
const dailySales = ref<SalesDataPoint[]>([])
const hourlySales = ref<HourlySales[]>([])
const topProducts = ref<ProductMargin[]>([])

// Computed
const revenueChange = computed(() => {
  if (!summary.value || !previousSummary.value || previousSummary.value.revenue === 0) return undefined
  return ((summary.value.revenue - previousSummary.value.revenue) / previousSummary.value.revenue) * 100
})

const receiptsChange = computed(() => {
  if (!summary.value || !previousSummary.value || previousSummary.value.receipts_count === 0) return undefined
  return ((summary.value.receipts_count - previousSummary.value.receipts_count) / previousSummary.value.receipts_count) * 100
})

const avgCheckChange = computed(() => {
  if (!summary.value || !previousSummary.value || previousSummary.value.avg_check === 0) return undefined
  return ((summary.value.avg_check - previousSummary.value.avg_check) / previousSummary.value.avg_check) * 100
})

const guestsChange = computed(() => {
  if (!summary.value || !previousSummary.value || previousSummary.value.guests_count === 0) return undefined
  return ((summary.value.guests_count - previousSummary.value.guests_count) / previousSummary.value.guests_count) * 100
})

const chartData = computed(() =>
  dailySales.value.map((d) => ({
    date: format(new Date(d.date), 'MMM d'),
    value: d.revenue,
  }))
)

const topProductsData = computed(() =>
  topProducts.value.slice(0, 5).map((p) => ({
    label: p.product_name.length > 20 ? p.product_name.substring(0, 20) + '...' : p.product_name,
    value: p.revenue,
  }))
)

// Format currency
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

const formatNumber = (value: number) => {
  return new Intl.NumberFormat('en-US').format(value)
}

// Fetch data
const fetchData = async () => {
  if (venuesStore.selectedVenueIds.length === 0) return

  loading.value = true
  try {
    const venueIds = venuesStore.selectedVenueIds
    const dateFrom = filtersStore.dateFrom
    const dateTo = filtersStore.dateTo

    // Fetch all data in parallel
    const [summaryData, comparisonData, dailyData, hourlyData, topData] = await Promise.all([
      reportsApi.getSalesSummary(dateFrom, dateTo, venueIds),
      reportsApi.getSalesComparison(dateFrom, dateTo, 'previous', venueIds),
      reportsApi.getSalesDaily(dateFrom, dateTo, venueIds),
      reportsApi.getSalesHourly(dateFrom, dateTo, venueIds),
      reportsApi.getTopSellers(dateFrom, dateTo, 10, 'revenue', venueIds),
    ])

    summary.value = summaryData
    previousSummary.value = comparisonData.previous
    dailySales.value = dailyData
    hourlySales.value = hourlyData
    topProducts.value = topData
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  } finally {
    loading.value = false
  }
}

// Watch for filter changes
watch(
  () => [filtersStore.dateFrom, filtersStore.dateTo, venuesStore.selectedVenueIds],
  () => {
    fetchData()
  },
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
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Dashboard</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Overview of your restaurant performance
      </p>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="Total Revenue"
        :value="summary ? formatCurrency(summary.revenue) : '-'"
        :change="revenueChange"
        change-label="vs previous period"
        icon="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        :loading="loading"
      />
      <StatCard
        title="Receipts"
        :value="summary ? formatNumber(summary.receipts_count) : '-'"
        :change="receiptsChange"
        change-label="vs previous period"
        icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
        :loading="loading"
      />
      <StatCard
        title="Average Check"
        :value="summary ? formatCurrency(summary.avg_check) : '-'"
        :change="avgCheckChange"
        change-label="vs previous period"
        icon="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
        :loading="loading"
      />
      <StatCard
        title="Guests"
        :value="summary ? formatNumber(summary.guests_count) : '-'"
        :change="guestsChange"
        change-label="vs previous period"
        icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
        :loading="loading"
      />
    </div>

    <!-- Charts row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Revenue chart -->
      <div class="lg:col-span-2 card p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Revenue Trend</h3>
        <LineChart
          :data="chartData"
          :loading="loading"
          :area-style="true"
          :value-formatter="formatCurrency"
        />
      </div>

      <!-- Top products -->
      <div class="card p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Top Products</h3>
        <BarChart
          :data="topProductsData"
          :loading="loading"
          :horizontal="true"
          :value-formatter="formatCurrency"
        />
      </div>
    </div>

    <!-- Hourly heatmap -->
    <div class="card p-6">
      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Hourly Revenue Distribution</h3>
      <HeatmapChart
        :data="hourlySales"
        :loading="loading"
        :value-formatter="formatCurrency"
      />
    </div>
  </div>
</template>
