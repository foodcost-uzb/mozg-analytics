<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useFiltersStore, useVenuesStore } from '@/stores'
import { reportsApi } from '@/api/reports'
import type { ABCAnalysis, GoListAnalysis, ProductMargin, CategoryAnalysis } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import PieChart from '@/components/charts/PieChart.vue'
import BarChart from '@/components/charts/BarChart.vue'

const filtersStore = useFiltersStore()
const venuesStore = useVenuesStore()

// Tabs
type Tab = 'abc' | 'golist' | 'margin' | 'categories'
const activeTab = ref<Tab>('abc')

// Data state
const loading = ref(false)
const abcAnalysis = ref<ABCAnalysis | null>(null)
const goListAnalysis = ref<GoListAnalysis | null>(null)
const marginData = ref<ProductMargin[]>([])
const categoryData = ref<CategoryAnalysis[]>([])

// ABC metric selector
const abcMetric = ref<'revenue' | 'profit' | 'quantity'>('revenue')

// Format helpers
const formatCurrency = (value: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(value)

const formatNumber = (value: number) =>
  new Intl.NumberFormat('en-US').format(value)

// ABC colors
const abcColors: Record<string, string> = {
  A: '#22c55e',
  B: '#f59e0b',
  C: '#ef4444',
}

// Go-List colors
const goListColors: Record<string, string> = {
  stars: '#fbbf24',
  workhorses: '#60a5fa',
  potential: '#34d399',
  standard: '#9ca3af',
  puzzles: '#a78bfa',
  dogs: '#f87171',
}

// Computed for charts
const abcChartData = computed(() =>
  abcAnalysis.value?.summary.map((s) => ({
    name: `Category ${s.category}`,
    value: s.revenue,
  })) || []
)

const categoryChartData = computed(() =>
  categoryData.value.slice(0, 8).map((c) => ({
    label: c.category_name.length > 15 ? c.category_name.substring(0, 15) + '...' : c.category_name,
    value: c.revenue,
  }))
)

// Table columns
const abcColumns = computed(() => [
  { key: 'product_name', label: 'Product' },
  { key: 'category_name', label: 'Category' },
  { key: 'quantity', label: 'Qty', align: 'right' as const, format: (v: number) => formatNumber(v) },
  { key: 'revenue', label: 'Revenue', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'profit', label: 'Profit', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'margin_percent', label: 'Margin', align: 'right' as const, format: (v: number) => `${v.toFixed(1)}%` },
  { key: 'revenue_percent', label: '% Total', align: 'right' as const, format: (v: number) => `${v.toFixed(2)}%` },
  {
    key: 'abc_category',
    label: 'ABC',
    align: 'center' as const,
    class: (v: string) => {
      const colors: Record<string, string> = {
        A: 'text-success-600 font-semibold',
        B: 'text-warning-600 font-semibold',
        C: 'text-danger-600 font-semibold',
      }
      return colors[v] || ''
    },
  },
])

const goListColumns = [
  { key: 'product_name', label: 'Product' },
  { key: 'abc_category', label: 'ABC', align: 'center' as const },
  { key: 'margin_percent', label: 'Margin', align: 'right' as const, format: (v: number) => `${v.toFixed(1)}%` },
  {
    key: 'go_list_category',
    label: 'Category',
    align: 'center' as const,
    format: (v: string) => v.charAt(0).toUpperCase() + v.slice(1),
  },
  { key: 'revenue', label: 'Revenue', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'recommendation', label: 'Recommendation' },
]

const marginColumns = [
  { key: 'product_name', label: 'Product' },
  { key: 'category_name', label: 'Category' },
  { key: 'quantity', label: 'Qty', align: 'right' as const, format: (v: number) => formatNumber(v) },
  { key: 'avg_price', label: 'Avg Price', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'avg_cost', label: 'Avg Cost', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'profit', label: 'Profit', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  {
    key: 'margin_percent',
    label: 'Margin %',
    align: 'right' as const,
    format: (v: number) => `${v.toFixed(1)}%`,
    class: (v: number) => v >= 50 ? 'text-success-600 font-medium' : v >= 30 ? 'text-warning-600' : 'text-danger-600',
  },
]

const categoryColumns = [
  { key: 'category_name', label: 'Category' },
  { key: 'revenue', label: 'Revenue', align: 'right' as const, format: (v: number) => formatCurrency(v) },
  { key: 'revenue_percent', label: '% Total', align: 'right' as const, format: (v: number) => `${v.toFixed(1)}%` },
  { key: 'products_count', label: 'Products', align: 'right' as const },
  { key: 'receipts_count', label: 'Receipts', align: 'right' as const, format: (v: number) => formatNumber(v) },
]

// Fetch data
const fetchData = async () => {
  if (venuesStore.selectedVenueIds.length === 0) return

  loading.value = true
  try {
    const venueIds = venuesStore.selectedVenueIds
    const dateFrom = filtersStore.dateFrom
    const dateTo = filtersStore.dateTo

    const [abcData, goListData, margins, categories] = await Promise.all([
      reportsApi.getABCAnalysis(dateFrom, dateTo, abcMetric.value, venueIds),
      reportsApi.getGoList(dateFrom, dateTo, undefined, venueIds),
      reportsApi.getMarginAnalysis(dateFrom, dateTo, 1, venueIds),
      reportsApi.getCategoryAnalysis(dateFrom, dateTo, venueIds),
    ])

    abcAnalysis.value = abcData
    goListAnalysis.value = goListData
    marginData.value = margins
    categoryData.value = categories
  } catch (error) {
    console.error('Failed to fetch menu data:', error)
  } finally {
    loading.value = false
  }
}

// Fetch ABC with new metric
const fetchABC = async () => {
  if (venuesStore.selectedVenueIds.length === 0) return

  loading.value = true
  try {
    abcAnalysis.value = await reportsApi.getABCAnalysis(
      filtersStore.dateFrom,
      filtersStore.dateTo,
      abcMetric.value,
      venuesStore.selectedVenueIds
    )
  } finally {
    loading.value = false
  }
}

watch(abcMetric, fetchABC)

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
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Menu Analysis</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        ABC analysis, margins, and menu optimization
      </p>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 dark:border-gray-700">
      <nav class="flex space-x-8">
        <button
          v-for="tab in [
            { key: 'abc', label: 'ABC Analysis' },
            { key: 'golist', label: 'Go-List' },
            { key: 'margin', label: 'Margins' },
            { key: 'categories', label: 'Categories' },
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
      <!-- ABC Analysis -->
      <div v-if="activeTab === 'abc'" class="space-y-6">
        <!-- Metric selector and summary -->
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-sm text-gray-500">Analyze by:</span>
            <select v-model="abcMetric" class="input w-40">
              <option value="revenue">Revenue</option>
              <option value="profit">Profit</option>
              <option value="quantity">Quantity</option>
            </select>
          </div>
          <div v-if="abcAnalysis" class="flex space-x-4 text-sm">
            <div v-for="s in abcAnalysis.summary" :key="s.category" class="flex items-center space-x-2">
              <span
                :class="[
                  'w-6 h-6 rounded flex items-center justify-center text-white font-semibold text-xs',
                  s.category === 'A' ? 'bg-success-500' : s.category === 'B' ? 'bg-warning-500' : 'bg-danger-500'
                ]"
              >
                {{ s.category }}
              </span>
              <span class="text-gray-600">{{ s.count }} items ({{ s.revenue_percent }}%)</span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div class="lg:col-span-3 card">
            <DataTable :columns="abcColumns" :data="abcAnalysis?.products || []" :loading="loading" row-key="product_id" />
          </div>
          <div class="card p-6">
            <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Distribution</h3>
            <PieChart :data="abcChartData" :loading="loading" :colors="['#22c55e', '#f59e0b', '#ef4444']" :value-formatter="formatCurrency" />
          </div>
        </div>
      </div>

      <!-- Go-List -->
      <div v-if="activeTab === 'golist'" class="space-y-6">
        <!-- Recommendations -->
        <div v-if="goListAnalysis?.recommendations.length" class="card p-4 bg-primary-50 dark:bg-primary-900/20 border-primary-200">
          <h3 class="font-medium text-primary-900 dark:text-primary-100 mb-2">Recommendations</h3>
          <ul class="space-y-1">
            <li v-for="(rec, i) in goListAnalysis.recommendations" :key="i" class="text-sm text-primary-700 dark:text-primary-300">
              {{ rec }}
            </li>
          </ul>
        </div>

        <!-- Summary badges -->
        <div v-if="goListAnalysis" class="flex flex-wrap gap-3">
          <div
            v-for="s in goListAnalysis.summary"
            :key="s.category"
            class="px-4 py-2 rounded-lg text-sm font-medium"
            :style="{ backgroundColor: goListColors[s.category] + '20', color: goListColors[s.category] }"
          >
            {{ s.category.charAt(0).toUpperCase() + s.category.slice(1) }}: {{ s.count }}
          </div>
        </div>

        <div class="card">
          <DataTable :columns="goListColumns" :data="goListAnalysis?.items || []" :loading="loading" row-key="product_id" />
        </div>
      </div>

      <!-- Margins -->
      <div v-if="activeTab === 'margin'" class="card">
        <DataTable :columns="marginColumns" :data="marginData" :loading="loading" row-key="product_id" />
      </div>

      <!-- Categories -->
      <div v-if="activeTab === 'categories'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 card">
          <DataTable :columns="categoryColumns" :data="categoryData" :loading="loading" row-key="category_id" />
        </div>
        <div class="card p-6">
          <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">Revenue by Category</h3>
          <BarChart :data="categoryChartData" :loading="loading" :horizontal="true" :value-formatter="formatCurrency" />
        </div>
      </div>
    </div>
  </div>
</template>
