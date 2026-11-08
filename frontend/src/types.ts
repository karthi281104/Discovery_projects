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
  is_verified_venue?: boolean
}

export type EventUpdateHistory = {
  timestamp: string
  source_url?: string
  changes: Record<string, { old: any; new: any }>
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
  // Autonomous Discovery Tracking Fields
  original_source_url?: string
  additional_source_urls?: string[]
  confidence_score?: number
  validation_outcome?: string | null
  content_hash?: string | null
  update_history?: EventUpdateHistory[]
  discovered_at?: string | null
  extracted_at?: string | null
  verified_at?: string | null
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


// ==========================================
// Milestone 3: Discovery Types
// ==========================================

export type SourceType = 'rss' | 'jsonld' | 'html' | 'api' | 'auto'

export type DiscoverySource = {
  id: number | string
  name: string
  base_url: string
  source_type: SourceType
  is_enabled: boolean
  region: string
  crawl_interval: number
  request_config: Record<string, any>
  last_crawl_time?: string | null
  last_success_time?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export type DiscoverySourceList = {
  items: DiscoverySource[]
  total: number
}

export type DiscoveryRun = {
  id: number | string
  source_id?: number | string | null
  source_name?: string | null
  started_at: string
  completed_at?: string | null
  status: 'running' | 'success' | 'failed' | 'partial'
  pages_checked: number
  candidates_found: number
  events_created: number
  events_updated: number
  duplicates_skipped: number
  validation_failures: number
  error_message?: string | null
  metrics?: Record<string, any>
}

export type DiscoveryRunList = {
  items: DiscoveryRun[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type DiscoveryMetrics = {
  // 14 Telemetry Counts
  queries_executed: number
  search_results_collected: number
  new_urls_discovered: number
  new_sources_identified: number
  pages_successfully_fetched: number
  pages_blocked_or_inaccessible: number
  event_candidates_extracted: number
  valid_events: number
  events_published: number
  candidates_requiring_review: number
  duplicates_detected: number
  events_updated: number
  source_failures: number
  discovery_execution_duration: number

  // Legacy fields
  total_sources?: number
  enabled_sources?: number
  sources_with_errors?: number
  last_successful_run?: string | null
  total_pages_checked?: number
  total_candidates_found?: number
  total_events_created?: number
  total_events_updated?: number
  total_duplicates_skipped?: number
  total_validation_failures?: number
}

export type AutonomousCampaignRequest = {
  region?: string
  categories?: string[]
  languages?: string[]
  max_pages?: number
}

export type AutonomousCampaignResult = {
  queries_executed: number
  search_results_collected: number
  new_urls_discovered: number
  new_sources_identified: number
  pages_successfully_fetched: number
  pages_blocked_or_inaccessible: number
  event_candidates_extracted: number
  valid_events: number
  events_published: number
  candidates_requiring_review: number
  duplicates_detected: number
  events_updated: number
  source_failures: number
  discovery_execution_duration: number
}

export type SearchCampaign = {
  id: number | string
  status: string
  region: string
  queries_executed: number
  results_collected: number
  sources_discovered: number
  duration_ms: number
  error_message?: string | null
}

export type DiscoveryCandidate = {
  title: string
  source_url: string
  source_name?: string | null
  start_date?: string | null
  validation_status: string
  rejection_reasons: string[]
  confidence_score: number
}

export type EventSource = {
  id: number | string
  event_id: number | string
  source_id: number | string
  source_name?: string | null
  external_event_id?: string | null
  source_event_url: string
  canonical_url: string
  content_hash: string
  first_seen: string
  last_seen: string
  last_checked: string
}
