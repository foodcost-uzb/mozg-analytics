import { apiClient } from './client'
import type {
  SalesSummary,
  SalesDataPoint,
  SalesComparison,
  VenueSales,
  HourlySales,
  PlanFact,
  ABCAnalysis,
  ProductMargin,
  GoListAnalysis,
  CategoryAnalysis,
} from '@/types'
import { format } from 'date-fns'

interface ReportParams {
  date_from: string
  date_to: string
  venue_ids?: string[]
}

function formatDate(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

function buildParams(
  dateFrom: Date,
  dateTo: Date,
  venueIds?: string[]
): ReportParams {
  const params: ReportParams = {
    date_from: formatDate(dateFrom),
    date_to: formatDate(dateTo),
  }
  if (venueIds && venueIds.length > 0) {
    params.venue_ids = venueIds
  }
  return params
}

export const reportsApi = {
  // Sales reports
  async getSalesSummary(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<SalesSummary> {
    return apiClient.get<SalesSummary>(
      '/reports/sales/summary',
      buildParams(dateFrom, dateTo, venueIds)
    )
  },

  async getSalesDaily(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<SalesDataPoint[]> {
    return apiClient.get<SalesDataPoint[]>(
      '/reports/sales/daily',
      buildParams(dateFrom, dateTo, venueIds)
    )
  },

  async getSalesComparison(
    dateFrom: Date,
    dateTo: Date,
    compareWith: 'previous' | 'year_ago' = 'previous',
    venueIds?: string[]
  ): Promise<SalesComparison> {
    return apiClient.get<SalesComparison>('/reports/sales/comparison', {
      ...buildParams(dateFrom, dateTo, venueIds),
      compare_with: compareWith,
    })
  },

  async getSalesByVenue(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<VenueSales[]> {
    return apiClient.get<VenueSales[]>(
      '/reports/sales/by-venue',
      buildParams(dateFrom, dateTo, venueIds)
    )
  },

  async getSalesHourly(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<HourlySales[]> {
    return apiClient.get<HourlySales[]>(
      '/reports/sales/hourly',
      buildParams(dateFrom, dateTo, venueIds)
    )
  },

  async getPlanFact(
    dateFrom: Date,
    dateTo: Date,
    targetRevenue?: number,
    venueIds?: string[]
  ): Promise<PlanFact> {
    return apiClient.get<PlanFact>('/reports/sales/plan-fact', {
      ...buildParams(dateFrom, dateTo, venueIds),
      target_revenue: targetRevenue,
    })
  },

  async getTopDays(
    dateFrom: Date,
    dateTo: Date,
    limit: number = 10,
    venueIds?: string[]
  ): Promise<SalesDataPoint[]> {
    return apiClient.get<SalesDataPoint[]>('/reports/sales/top-days', {
      ...buildParams(dateFrom, dateTo, venueIds),
      limit,
    })
  },

  async getWeekdayAnalysis(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<Record<string, { avg_revenue: number; avg_receipts: number; avg_check: number }>> {
    return apiClient.get('/reports/sales/weekday-analysis', buildParams(dateFrom, dateTo, venueIds))
  },

  // Menu analysis reports
  async getABCAnalysis(
    dateFrom: Date,
    dateTo: Date,
    metric: 'revenue' | 'profit' | 'quantity' = 'revenue',
    venueIds?: string[]
  ): Promise<ABCAnalysis> {
    return apiClient.get<ABCAnalysis>('/reports/menu/abc', {
      ...buildParams(dateFrom, dateTo, venueIds),
      metric,
    })
  },

  async getMarginAnalysis(
    dateFrom: Date,
    dateTo: Date,
    minQuantity: number = 1,
    venueIds?: string[]
  ): Promise<ProductMargin[]> {
    return apiClient.get<ProductMargin[]>('/reports/menu/margin', {
      ...buildParams(dateFrom, dateTo, venueIds),
      min_quantity: minQuantity,
    })
  },

  async getGoList(
    dateFrom: Date,
    dateTo: Date,
    marginThreshold?: number,
    venueIds?: string[]
  ): Promise<GoListAnalysis> {
    return apiClient.get<GoListAnalysis>('/reports/menu/go-list', {
      ...buildParams(dateFrom, dateTo, venueIds),
      margin_threshold: marginThreshold,
    })
  },

  async getTopSellers(
    dateFrom: Date,
    dateTo: Date,
    limit: number = 10,
    by: 'revenue' | 'quantity' | 'profit' = 'revenue',
    venueIds?: string[]
  ): Promise<ProductMargin[]> {
    return apiClient.get<ProductMargin[]>('/reports/menu/top-sellers', {
      ...buildParams(dateFrom, dateTo, venueIds),
      limit,
      by,
    })
  },

  async getWorstSellers(
    dateFrom: Date,
    dateTo: Date,
    limit: number = 10,
    minQuantity: number = 5,
    venueIds?: string[]
  ): Promise<ProductMargin[]> {
    return apiClient.get<ProductMargin[]>('/reports/menu/worst-sellers', {
      ...buildParams(dateFrom, dateTo, venueIds),
      limit,
      min_quantity: minQuantity,
    })
  },

  async getCategoryAnalysis(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<CategoryAnalysis[]> {
    return apiClient.get<CategoryAnalysis[]>(
      '/reports/menu/categories',
      buildParams(dateFrom, dateTo, venueIds)
    )
  },

  // Export
  async exportSales(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<Blob> {
    return apiClient.download('/reports/export/sales', buildParams(dateFrom, dateTo, venueIds))
  },

  async exportABC(
    dateFrom: Date,
    dateTo: Date,
    metric: 'revenue' | 'profit' | 'quantity' = 'revenue',
    venueIds?: string[]
  ): Promise<Blob> {
    return apiClient.download('/reports/export/abc', {
      ...buildParams(dateFrom, dateTo, venueIds),
      metric,
    })
  },

  async exportGoList(
    dateFrom: Date,
    dateTo: Date,
    venueIds?: string[]
  ): Promise<Blob> {
    return apiClient.download('/reports/export/go-list', buildParams(dateFrom, dateTo, venueIds))
  },
}
