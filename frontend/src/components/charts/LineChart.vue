<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const props = defineProps<{
  title?: string
  data: { date: string; value: number }[]
  loading?: boolean
  color?: string
  areaStyle?: boolean
  valueFormatter?: (value: number) => string
}>()

const option = computed(() => ({
  title: props.title ? { text: props.title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
  tooltip: {
    trigger: 'axis',
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
    type: 'category',
    boundaryGap: false,
    data: props.data.map((d) => d.date),
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisLabel: { color: '#6b7280' },
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisLabel: {
      color: '#6b7280',
      formatter: props.valueFormatter,
    },
    splitLine: { lineStyle: { color: '#e5e7eb' } },
  },
  series: [
    {
      type: 'line',
      data: props.data.map((d) => d.value),
      smooth: true,
      lineStyle: { color: props.color || '#3b82f6', width: 2 },
      itemStyle: { color: props.color || '#3b82f6' },
      areaStyle: props.areaStyle
        ? {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: (props.color || '#3b82f6') + '40' },
                { offset: 1, color: (props.color || '#3b82f6') + '00' },
              ],
            },
          }
        : undefined,
    },
  ],
}))
</script>

<template>
  <div class="relative">
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-800/50">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
    </div>
    <v-chart :option="option" autoresize style="height: 300px" />
  </div>
</template>
