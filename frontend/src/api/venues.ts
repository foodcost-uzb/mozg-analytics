import { apiClient } from './client'
import type { Venue, VenueListItem, SyncStatus } from '@/types'

export interface CreateVenueData {
  name: string
  address?: string
  city?: string
  timezone?: string
  pos_type: 'iiko' | 'rkeeper'
  pos_config: {
    organization_id?: string
    api_login?: string
    server_url?: string
    api_key?: string
  }
}

export interface UpdateVenueData {
  name?: string
  address?: string
  city?: string
  timezone?: string
  is_active?: boolean
  pos_config?: Record<string, unknown>
}

export interface SyncStatusResponse {
  venue_id: string
  status: SyncStatus
  last_sync_at: string | null
  error: string | null
}

export const venuesApi = {
  async list(): Promise<VenueListItem[]> {
    return apiClient.get<VenueListItem[]>('/venues')
  },

  async get(id: string): Promise<Venue> {
    return apiClient.get<Venue>(`/venues/${id}`)
  },

  async create(data: CreateVenueData): Promise<Venue> {
    return apiClient.post<Venue>('/venues', data)
  },

  async update(id: string, data: UpdateVenueData): Promise<Venue> {
    return apiClient.patch<Venue>(`/venues/${id}`, data)
  },

  async delete(id: string): Promise<void> {
    return apiClient.delete(`/venues/${id}`)
  },

  async triggerSync(id: string, fullSync: boolean = false): Promise<void> {
    await apiClient.post(`/venues/${id}/sync`, { full_sync: fullSync })
  },

  async getSyncStatus(id: string): Promise<SyncStatusResponse> {
    return apiClient.get<SyncStatusResponse>(`/venues/${id}/sync/status`)
  },
}
