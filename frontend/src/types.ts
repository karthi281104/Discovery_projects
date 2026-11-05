export type EventType =
  | 'hackathon'
  | 'conference'
  | 'workshop'
  | 'webinar'
  | 'competition'
  | 'symposium'
  | 'open_source'
  | 'startup'
  | 'research'
  | 'other'

export type EventMode = 'online' | 'offline' | 'hybrid'
export type EventStatus = 'draft' | 'pending' | 'published' | 'rejected' | 'cancelled' | 'expired'

export type Category = {
  id: number | string
  name: string
  slug: string
  description?: string | null
  icon?: string | null
  is_active?: boolean
}

export type Location = {
  id: number | string
  name: string
  city: string
  district?: string | null
  state: string
  address?: string | null
  latitude?: number | null
  longitude?: number | null
  is_active?: boolean
}

export type Event = {
  id: number | string
  title: string
  slug: string
  short_description?: string | null
  description: string
  organizer_name: string
  organizer_website?: string | null
  category_id?: number | string | null
  category?: Category | null
  location_id?: number | string | null
  location?: Location | null
  event_type: EventType
  mode: EventMode
  start_date: string
  end_date?: string | null
  registration_deadline?: string | null
  registration_url: string
  official_website?: string | null
  state: string
  district?: string | null
  city?: string | null
  venue?: string | null
  eligibility?: string | null
  participation_fee?: number | null
  currency: string
  banner_url?: string | null
  contact_email?: string | null
  tags: string[]
  status: EventStatus
  is_published: boolean
  is_featured: boolean
  created_at?: string | null
  updated_at?: string | null
}

export type EventList = {
  items: Event[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type AdminMetrics = {
  total_events: number
  published_events: number
  draft_events: number
  pending_events: number
  rejected_events: number
  cancelled_events: number
  expired_events: number
  featured_events: number
  total_categories: number
  total_locations: number
}
