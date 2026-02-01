<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'

use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  title?: string
  data: { name: string; value: number }[]
  loading?: boolean
  colors?: string[]
  donut?: boolean
  valueFormatter?: (value: number) => string
}>()

const defaultColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

const option = computed(() => ({
  title: props.title ? { text: props.title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
  tooltip: {
    trigger: 'item',
    formatter: (params: { name: string; value: number; percent: number }) => {
      const value = props.valueFormatter ? props.valueFormatter(params.value) : params.value
      return `${params.name}<br/>${value} (${params.percent}%)`
    },
  },
  legend: {
    bottom: '0',
    left: 'center',
  },
  series: [
    {
      type: 'pie',
      radius: props.donut ? ['40%', '70%'] : '70%',
      center: ['50%', '45%'],
      data: props.data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
      itemStyle: {
        borderRadius: 4,
        borderColor: '#fff',
        borderWidth: 2,
      },
      color: props.colors || defaultColors,
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
