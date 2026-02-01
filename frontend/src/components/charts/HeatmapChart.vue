<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  VisualMapComponent,
} from 'echarts/components'

use([CanvasRenderer, HeatmapChart, TitleComponent, TooltipComponent, GridComponent, VisualMapComponent])

const props = defineProps<{
  title?: string
  data: { hour: number; revenue: number }[]
  loading?: boolean
  valueFormatter?: (value: number) => string
}>()

const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)

const option = computed(() => {
  const maxValue = Math.max(...props.data.map((d) => d.revenue), 1)
  const heatmapData = props.data.map((d) => [d.hour, 0, d.revenue])

  return {
    title: props.title ? { text: props.title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: {
      position: 'top',
      formatter: (params: { data: [number, number, number] }) => {
        const hour = params.data[0]
        const value = props.valueFormatter ? props.valueFormatter(params.data[2]) : params.data[2]
        return `${hour}:00 - ${hour + 1}:00<br/>Revenue: ${value}`
      },
    },
    grid: {
      left: '3%',
      right: '10%',
      bottom: '10%',
      top: props.title ? '15%' : '5%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: hours,
      splitArea: { show: true },
      axisLabel: {
        color: '#6b7280',
        interval: 3,
      },
    },
    yAxis: {
      type: 'category',
      data: ['Revenue'],
      splitArea: { show: true },
      axisLabel: { show: false },
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: true,
      orient: 'vertical',
      right: '2%',
      bottom: '20%',
      inRange: {
        color: ['#dbeafe', '#3b82f6', '#1e40af'],
      },
      textStyle: { color: '#6b7280' },
    },
    series: [
      {
        type: 'heatmap',
        data: heatmapData,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
        },
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
    <v-chart :option="option" autoresize style="height: 200px" />
  </div>
</template>
