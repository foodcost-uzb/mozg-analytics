<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const props = defineProps<{
  title?: string
  data: { label: string; value: number }[]
  loading?: boolean
  color?: string
  horizontal?: boolean
  valueFormatter?: (value: number) => string
}>()

const option = computed(() => {
  const xAxisData = props.data.map((d) => d.label)
  const seriesData = props.data.map((d) => d.value)

  return {
    title: props.title ? { text: props.title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: { name: string; value: number }[]) => {
        const item = params[0]
        const value = props.valueFormatter ? props.valueFormatter(item.value) : item.value
        return `${item.name}<br/>${value}`
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: props.horizontal ? 'value' : 'category',
      data: props.horizontal ? undefined : xAxisData,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#6b7280', rotate: props.horizontal ? 0 : 45 },
    },
    yAxis: {
      type: props.horizontal ? 'category' : 'value',
      data: props.horizontal ? xAxisData : undefined,
      axisLine: { show: false },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [
      {
        type: 'bar',
        data: seriesData,
        itemStyle: {
          color: props.color || '#3b82f6',
          borderRadius: [4, 4, 0, 0],
        },
        barMaxWidth: 40,
      },
    ],
  }
})
</script>

<template>
  <div class="relative">
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-800/50">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
    </div>
    <v-chart :option="option" autoresize style="height: 300px" />
  </div>
</template>
