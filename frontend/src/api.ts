import type { Category, Event, EventList, Location } from './types'

const request = async <T>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | { detail?: string } } | null
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(`${detail} (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const getCategories = () => request<Category[]>('/categories')
export const getLocations = () => request<Location[]>('/locations')
export const getEvents = (params: Record<string, string | number | undefined> = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return request<EventList>(`/events${query.toString() ? `?${query}` : ''}`)
}
export const getEvent = (slug: string) => request<Event>(`/events/${encodeURIComponent(slug)}`)
export const getFeaturedEvents = () => request<Event[]>('/events/featured')
export const getUpcomingEvents = () => request<Event[]>('/events/upcoming')

export type AdminEventInput = Partial<Omit<Event, 'id' | 'category' | 'created_at' | 'updated_at'>> & Pick<Event, 'title' | 'description' | 'organizer_name' | 'event_type' | 'mode' | 'start_date' | 'end_date' | 'registration_url'>

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
export const getAdminEvents = (params: Record<string, string | number | undefined> = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return adminRequest<EventList>(`/admin/events${query.toString() ? `?${query}` : ''}`)
}
export const createAdminEvent = (event: AdminEventInput) => adminRequest<Event>('/admin/events', { method: 'POST', body: JSON.stringify(event) })
export const updateAdminEvent = (id: string, event: Partial<AdminEventInput>) => adminRequest<Event>(`/admin/events/${id}`, { method: 'PUT', body: JSON.stringify(event) })
export const deleteAdminEvent = (id: string) => adminRequest<void>(`/admin/events/${id}`, { method: 'DELETE' })
export const updateEventAction = (id: string, action: 'publish' | 'reject' | 'feature') =>
  adminRequest<Event>(`/admin/events/${id}/${action}`, { method: 'PATCH' })
