import type {
  AdminMetrics,
  AutonomousCampaignRequest,
  AutonomousCampaignResult,
  Category,
  DiscoveryCandidate,
  DiscoveryMetrics,
  DiscoveryRun,
  DiscoveryRunList,
  DiscoverySource,
  DiscoverySourceList,
  Event,
  EventList,
  EventSource,
  Location,
  SearchCampaign,
} from './types'

const request = async <T>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string | { detail?: string } } | null
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(`${detail} (${response.status})`)
  }
  if (response.status === 204) {
    return null as T
  }
  return response.json() as Promise<T>
}

export const getCategories = () => request<Category[]>('/categories')
export const getLocations = () => request<Location[]>('/locations')
export const getEvents = (params: Record<string, string | number | boolean | undefined> = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return request<EventList>(`/events${query.toString() ? `?${query}` : ''}`)
}
export const getEvent = (slug: string) => request<Event>(`/events/${encodeURIComponent(slug)}`)
export const getFeaturedEvents = () => request<Event[]>('/events/featured')
export const getUpcomingEvents = () => request<Event[]>('/events/upcoming')

export type AdminEventInput = Partial<Omit<Event, 'id' | 'category' | 'location' | 'created_at' | 'updated_at'>> &
  Pick<Event, 'title' | 'description' | 'organizer_name' | 'event_type' | 'mode' | 'start_date' | 'registration_url'>

const adminRequest = <T>(path: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('admin_token')
  return request<T>(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers ?? {}) },
  })
}

export const adminLogin = (email: string, password: string) =>
  request<{ access_token: string; token_type: string }>('/admin/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const getAdminMetrics = () => adminRequest<AdminMetrics>('/admin/metrics')

export const getAdminEvents = (params: Record<string, string | number | boolean | undefined> = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return adminRequest<EventList>(`/admin/events${query.toString() ? `?${query}` : ''}`)
}

export const getAdminEvent = (id: string | number) => adminRequest<Event>(`/admin/events/${id}`)

export const createAdminEvent = (event: AdminEventInput) =>
  adminRequest<Event>('/admin/events', { method: 'POST', body: JSON.stringify(event) })

export const updateAdminEvent = (id: string | number, event: Partial<AdminEventInput>) =>
  adminRequest<Event>(`/admin/events/${id}`, { method: 'PUT', body: JSON.stringify(event) })

export const deleteAdminEvent = (id: string | number) =>
  adminRequest<void>(`/admin/events/${id}`, { method: 'DELETE' })

export const updateEventAction = (
  id: string | number,
  action: 'publish' | 'reject' | 'feature' | 'unfeature',
) => {
  if (action === 'feature') {
    return adminRequest<Event>(`/admin/events/${id}/feature?state=true`, { method: 'PATCH' })
  }
  if (action === 'unfeature') {
    return adminRequest<Event>(`/admin/events/${id}/unfeature`, { method: 'PATCH' })
  }
  return adminRequest<Event>(`/admin/events/${id}/${action}`, { method: 'PATCH' })
}

// Categories Admin API
export const getAdminCategories = () => adminRequest<Category[]>('/admin/categories')
export const createAdminCategory = (data: Partial<Category>) =>
  adminRequest<Category>('/admin/categories', { method: 'POST', body: JSON.stringify(data) })
export const updateAdminCategory = (id: string | number, data: Partial<Category>) =>
  adminRequest<Category>(`/admin/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deactivateAdminCategory = (id: string | number) =>
  adminRequest<Category>(`/admin/categories/${id}/deactivate`, { method: 'PATCH' })
export const deleteAdminCategory = (id: string | number) =>
  adminRequest<void>(`/admin/categories/${id}`, { method: 'DELETE' })

// Locations Admin API
export const getAdminLocations = () => adminRequest<Location[]>('/admin/locations')
export const createAdminLocation = (data: Partial<Location>) =>
  adminRequest<Location>('/admin/locations', { method: 'POST', body: JSON.stringify(data) })
export const updateAdminLocation = (id: string | number, data: Partial<Location>) =>
  adminRequest<Location>(`/admin/locations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteAdminLocation = (id: string | number) =>
  adminRequest<void>(`/admin/locations/${id}`, { method: 'DELETE' })


// ==========================================
// Milestone 3: Discovery API Endpoints
// ==========================================

export const getAdminDiscoverySources = (enabledOnly = false) =>
  adminRequest<DiscoverySourceList>(`/admin/discovery/sources${enabledOnly ? '?enabled_only=true' : ''}`)

export const createAdminDiscoverySource = (data: Partial<DiscoverySource>) =>
  adminRequest<DiscoverySource>('/admin/discovery/sources', { method: 'POST', body: JSON.stringify(data) })

export const updateAdminDiscoverySource = (id: string | number, data: Partial<DiscoverySource>) =>
  adminRequest<DiscoverySource>(`/admin/discovery/sources/${id}`, { method: 'PUT', body: JSON.stringify(data) })

export const toggleAdminDiscoverySource = (id: string | number) =>
  adminRequest<DiscoverySource>(`/admin/discovery/sources/${id}/toggle`, { method: 'PATCH' })

export const deleteAdminDiscoverySource = (id: string | number) =>
  adminRequest<void>(`/admin/discovery/sources/${id}`, { method: 'DELETE' })

export const getAdminDiscoveryRuns = (page = 1, pageSize = 20, status?: string) => {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (status) query.set('status', status)
  return adminRequest<DiscoveryRunList>(`/admin/discovery/runs?${query.toString()}`)
}

export const getAdminDiscoveryRunDetail = (runId: string | number) =>
  adminRequest<DiscoveryRun>(`/admin/discovery/runs/${runId}`)

export const triggerAdminDiscoveryAll = () =>
  adminRequest<DiscoveryRun[]>('/admin/discovery/run', { method: 'POST' })

export const triggerAdminDiscoverySource = (sourceId: string | number) =>
  adminRequest<DiscoveryRun>(`/admin/discovery/run/${sourceId}`, { method: 'POST' })

export const getAdminDiscoveryMetrics = () =>
  adminRequest<DiscoveryMetrics>('/admin/discovery/metrics')

export const triggerAdminSearchCampaign = () =>
  adminRequest<SearchCampaign>('/admin/discovery/search', { method: 'POST' })

export const triggerAdminAutonomousCampaign = (params?: AutonomousCampaignRequest) =>
  adminRequest<AutonomousCampaignResult>('/admin/discovery/autonomous-campaign', {
    method: 'POST',
    body: JSON.stringify(
      params || {
        region: 'Tamil Nadu',
        categories: ['Hackathon', 'Symposium', 'Workshop', 'Tech Meetup'],
        languages: ['en', 'ta'],
        max_pages: 3,
      }
    ),
  })

export const getAdminSearchCampaigns = () =>
  adminRequest<SearchCampaign[]>('/admin/discovery/search/campaigns')

export const getAdminDiscoveryCandidates = (limit = 50) =>
  adminRequest<DiscoveryCandidate[]>(`/admin/discovery/candidates?limit=${limit}`)

export const getAdminReviewQueue = (limit = 50) =>
  adminRequest<Event[]>(`/admin/discovery/review-queue?limit=${limit}`)

export const getAdminPublishedEvents = (limit = 50) =>
  adminRequest<Event[]>(`/admin/discovery/published-events?limit=${limit}`)

export const getAdminEventSources = (eventId: string | number) =>
  adminRequest<EventSource[]>(`/admin/discovery/events/${eventId}/sources`)
