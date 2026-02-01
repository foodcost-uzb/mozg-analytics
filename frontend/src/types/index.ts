// ==================== Auth Types ====================

export interface User {
  id: string
  organization_id: string
  email: string | null
  phone: string | null
  first_name: string
  last_name: string | null
  role: UserRole
  telegram_id: number | null
  telegram_username: string | null
  avatar_url: string | null
  is_active: boolean
  last_login_at: string | null
  allowed_venue_ids: string[] | null
  created_at: string
  updated_at: string
}

export type UserRole = 'owner' | 'admin' | 'manager' | 'analyst' | 'viewer'

export interface Organization {
  id: string
  name: string
  slug: string
  is_active: boolean
  settings: Record<string, unknown> | null
  subscription_plan: string
  subscription_expires_at: string | null
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// ==================== Venue Types ====================

export type POSType = 'iiko' | 'rkeeper'
export type SyncStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export interface Venue {
  id: string
  organization_id: string
  name: string
  address: string | null
  city: string | null
  timezone: string
  pos_type: POSType
  pos_config: Record<string, unknown>
  is_active: boolean
  last_sync_at: string | null
  sync_status: SyncStatus
  sync_error: string | null
  created_at: string
  updated_at: string
}

export interface VenueListItem {
  id: string
  name: string
  address: string | null
  city: string | null
  pos_type: POSType
  is_active: boolean
  last_sync_at: string | null
  sync_status: SyncStatus
}

// ==================== Report Types ====================

export interface DateRangeParams {
  date_from: string
  date_to: string
  venue_ids?: string[]
}

export interface SalesSummary {
  revenue: number
  receipts_count: number
  avg_check: number
  guests_count: number
  items_count: number
  items_per_receipt: number
  revenue_per_guest: number
  total_discount: number
}

export interface SalesDataPoint {
  date: string
  revenue: number
  receipts_count: number
  avg_check: number
  guests_count: number
}

export interface SalesComparison {
  current: SalesSummary
  previous: SalesSummary
  revenue_diff: number
  revenue_diff_percent: number
  receipts_diff: number
  receipts_diff_percent: number
  avg_check_diff: number
  avg_check_diff_percent: number
  guests_diff: number
  guests_diff_percent: number
}

export interface VenueSales {
  venue_id: string
  venue_name: string
  revenue: number
  receipts_count: number
  avg_check: number
  guests_count: number
  revenue_percent: number
}

export interface HourlySales {
  hour: number
  revenue: number
  receipts_count: number
  avg_revenue: number
}

export interface PlanFact {
  actual_revenue: number
  target_revenue: number
  completion_percent: number
  remaining: number
  receipts_count: number
  avg_check: number
}

// ==================== Menu Analysis Types ====================

export type ABCCategory = 'A' | 'B' | 'C'
export type GoListCategory = 'stars' | 'workhorses' | 'puzzles' | 'dogs' | 'potential' | 'standard'

export interface ProductABC {
  product_id: string
  product_name: string
  category_name: string | null
  quantity: number
  revenue: number
  cost: number
  profit: number
  margin_percent: number
  revenue_percent: number
  cumulative_percent: number
  abc_category: ABCCategory
}

export interface ABCSummary {
  category: ABCCategory
  count: number
  revenue: number
  profit: number
  revenue_percent: number
}

export interface ABCAnalysis {
  products: ProductABC[]
  summary: ABCSummary[]
  total_revenue: number
  total_profit: number
}

export interface ProductMargin {
  product_id: string
  product_name: string
  category_name: string | null
  quantity: number
  revenue: number
  cost: number
  profit: number
  margin_percent: number
  avg_price: number
  avg_cost: number
}

export interface GoListItem {
  product_id: string
  product_name: string
  category_name: string | null
  abc_category: ABCCategory
  margin_percent: number
  go_list_category: GoListCategory
  recommendation: string
  revenue: number
  profit: number
}

export interface GoListSummary {
  category: GoListCategory
  count: number
  revenue: number
  profit: number
}

export interface GoListAnalysis {
  items: GoListItem[]
  summary: GoListSummary[]
  recommendations: string[]
}

export interface CategoryAnalysis {
  category_id: string
  category_name: string
  quantity: number
  revenue: number
  revenue_percent: number
  products_count: number
  receipts_count: number
}

// ==================== Filter Types ====================

export interface ReportFilters {
  dateFrom: Date
  dateTo: Date
  venueIds: string[]
  compareWith?: 'previous' | 'year_ago'
}

// ==================== API Response Types ====================

export interface ApiError {
  detail: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}
