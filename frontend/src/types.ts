export type EventType = 'hackathon' | 'conference' | 'workshop' | 'webinar' | 'competition' | 'symposium' | 'open_source' | 'startup' | 'research' | 'other'
export type EventMode = 'online' | 'offline' | 'hybrid'
export type EventStatus = 'draft' | 'pending' | 'published' | 'rejected' | 'cancelled' | 'expired'

export type Category = {
  id: string
  name: string
  slug: string
  description?: string | null
  icon?: string | null
}

export type Location = {
  id: string
  state: string
  district?: string | null
  city: string
}

export type Event = {
  id: string
  title: string
  slug: string
  short_description?: string | null
  description: string
  organizer_name: string
  organizer_website?: string | null
  category_id?: string | null
  category?: Category | null
  event_type: EventType
  mode: EventMode
  start_date: string
  end_date: string
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
  is_featured: boolean
  created_at: string
  updated_at: string
}

export type EventList = {
  items: Event[]
  total: number
  page: number
  page_size: number
  pages: number
}
