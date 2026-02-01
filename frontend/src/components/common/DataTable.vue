<script setup lang="ts" generic="T extends Record<string, unknown>">
import { computed } from 'vue'

export interface Column<T> {
  key: keyof T | string
  label: string
  align?: 'left' | 'center' | 'right'
  width?: string
  format?: (value: unknown, row: T) => string
  class?: string | ((value: unknown, row: T) => string)
}

const props = defineProps<{
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: string
  rowKey?: keyof T
}>()

const emit = defineEmits<{
  'row-click': [row: T]
}>()

const getCellValue = (row: T, column: Column<T>): string => {
  const keys = String(column.key).split('.')
  let value: unknown = row
  for (const key of keys) {
    value = (value as Record<string, unknown>)?.[key]
  }
  if (column.format) {
    return column.format(value, row)
  }
  return String(value ?? '-')
}

const getCellClass = (row: T, column: Column<T>): string => {
  if (typeof column.class === 'function') {
    const keys = String(column.key).split('.')
    let value: unknown = row
    for (const key of keys) {
      value = (value as Record<string, unknown>)?.[key]
    }
    return column.class(value, row)
  }
  return column.class || ''
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
      <thead class="bg-gray-50 dark:bg-gray-800">
        <tr>
          <th
            v-for="column in columns"
            :key="String(column.key)"
            :style="{ width: column.width }"
            :class="[
              'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider',
              column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left'
            ]"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
        <!-- Loading state -->
        <template v-if="loading">
          <tr v-for="i in 5" :key="i">
            <td v-for="column in columns" :key="String(column.key)" class="px-4 py-4">
              <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            </td>
          </tr>
        </template>

        <!-- Empty state -->
        <tr v-else-if="data.length === 0">
          <td :colspan="columns.length" class="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
            {{ emptyMessage || 'No data available' }}
          </td>
        </tr>

        <!-- Data rows -->
        <tr
          v-else
          v-for="(row, index) in data"
          :key="rowKey ? String(row[rowKey]) : index"
          class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          @click="emit('row-click', row)"
        >
          <td
            v-for="column in columns"
            :key="String(column.key)"
            :class="[
              'px-4 py-4 text-sm',
              column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left',
              getCellClass(row, column)
            ]"
          >
            <slot :name="String(column.key)" :value="getCellValue(row, column)" :row="row">
              {{ getCellValue(row, column) }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
