import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { DiscoveryMonitor } from '../DiscoveryMonitor'
import * as api from '../api'
import type {
  DiscoveryCandidate,
  DiscoveryMetrics,
  DiscoveryRun,
  DiscoverySource,
} from '../types'

const mockMetrics: DiscoveryMetrics = {
  queries_executed: 10,
  search_results_collected: 45,
  new_urls_discovered: 25,
  new_sources_identified: 2,
  pages_successfully_fetched: 5,
  pages_blocked_or_inaccessible: 1,
  event_candidates_extracted: 12,
  valid_events: 10,
  events_published: 8,
  candidates_requiring_review: 2,
  duplicates_detected: 2,
  events_updated: 2,
  source_failures: 0,
  discovery_execution_duration: 14.5,

  total_sources: 2,
  enabled_sources: 2,
  sources_with_errors: 0,
  last_successful_run: '2026-11-20T10:00:00Z',
  total_pages_checked: 5,
  total_candidates_found: 12,
  total_events_created: 8,
  total_events_updated: 2,
  total_duplicates_skipped: 2,
  total_validation_failures: 1,
}

const mockSources: DiscoverySource[] = [
  {
    id: 1,
    name: 'KnowAFest RSS Feed',
    base_url: 'https://example.com/knowafest.xml',
    source_type: 'rss',
    is_enabled: true,
    region: 'Tamil Nadu',
    crawl_interval: 60,
    request_config: {},
    last_crawl_time: '2026-11-20T09:00:00Z',
    last_success_time: '2026-11-20T09:00:00Z',
    last_error: null,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
]

const mockRuns: DiscoveryRun[] = [
  {
    id: 101,
    source_id: 1,
    source_name: 'KnowAFest RSS Feed',
    started_at: '2026-11-20T09:00:00Z',
    completed_at: '2026-11-20T09:01:00Z',
    status: 'success',
    pages_checked: 1,
    candidates_found: 4,
    events_created: 3,
    events_updated: 0,
    duplicates_skipped: 1,
    validation_failures: 0,
    metrics: {},
  },
]

const mockCandidates: DiscoveryCandidate[] = [
  {
    title: 'Generic Event Title',
    source_url: 'https://example.com/invalid-event',
    source_name: 'KnowAFest RSS Feed',
    validation_status: 'invalid',
    rejection_reasons: ['Title is generic or boilerplate'],
    confidence_score: 0.2,
  },
]

describe('DiscoveryMonitor Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'getAdminDiscoveryMetrics').mockResolvedValue(mockMetrics)
    vi.spyOn(api, 'getAdminDiscoverySources').mockResolvedValue({ items: mockSources, total: 1 })
    vi.spyOn(api, 'getAdminDiscoveryRuns').mockResolvedValue({ items: mockRuns, total: 1, page: 1, page_size: 20, pages: 1 })
    vi.spyOn(api, 'getAdminDiscoveryCandidates').mockResolvedValue(mockCandidates)
    vi.spyOn(api, 'getAdminReviewQueue').mockResolvedValue([])
    vi.spyOn(api, 'getAdminPublishedEvents').mockResolvedValue([])
  })

  it('renders discovery metrics, sources table, and recent runs', async () => {
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getAllByText('KnowAFest RSS Feed')[0]).toBeDefined()
    })

    expect(screen.getByText('Queries Executed')).toBeDefined()
    expect(screen.getByText('Events Published')).toBeDefined()
    expect(screen.getByText('Events Updated')).toBeDefined()
    expect(screen.getByText('Trigger All Sources')).toBeDefined()
    expect(screen.getByText('+ Add New Source')).toBeDefined()
    expect(screen.getByText('Recent Discovery Runs (1)')).toBeDefined()
  })

  it('triggers all sources discovery run on button click', async () => {
    const triggerSpy = vi.spyOn(api, 'triggerAdminDiscoveryAll').mockResolvedValue(mockRuns)
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getByText('Trigger All Sources')).toBeDefined()
    })

    fireEvent.click(screen.getByText('Trigger All Sources'))

    await waitFor(() => {
      expect(triggerSpy).toHaveBeenCalledTimes(1)
    })
  })

  it('triggers individual source run on button click', async () => {
    const triggerSourceSpy = vi.spyOn(api, 'triggerAdminDiscoverySource').mockResolvedValue(mockRuns[0])
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getByText('Run Now')).toBeDefined()
    })

    fireEvent.click(screen.getByText('Run Now'))

    await waitFor(() => {
      expect(triggerSourceSpy).toHaveBeenCalledWith(1)
    })
  })

  it('toggles source enabled status on button click', async () => {
    const toggleSpy = vi.spyOn(api, 'toggleAdminDiscoverySource').mockResolvedValue({
      ...mockSources[0],
      is_enabled: false,
    })
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getByText('ENABLED')).toBeDefined()
    })

    fireEvent.click(screen.getByText('ENABLED'))

    await waitFor(() => {
      expect(toggleSpy).toHaveBeenCalledWith(1)
    })
  })

  it('renders candidate exceptions table with rejection reasons', async () => {
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getByText(/Exceptions/i)).toBeDefined()
    })

    fireEvent.click(screen.getByText(/Exceptions/i))

    await waitFor(() => {
      expect(screen.getByText('Generic Event Title')).toBeDefined()
      expect(screen.getByText('Title is generic or boilerplate')).toBeDefined()
    })
  })

  it('renders review queue and opens the evidence drawer with all fields and update history', async () => {
    const mockReviewEvent = {
      id: 201,
      title: 'Salem AI Symposium 2026',
      slug: 'salem-ai-symposium-2026',
      description: 'Annual AI symposium in Salem',
      organizer_name: 'Salem Tech',
      event_type: 'symposium' as const,
      mode: 'offline' as const,
      start_date: '2026-11-25T09:00:00Z',
      registration_url: 'https://example.com/register',
      state: 'Tamil Nadu',
      city: 'Salem',
      venue: 'Salem Engineering College',
      tags: ['ai', 'symposium'],
      status: 'pending' as const,
      is_published: false,
      is_featured: false,
      currency: 'INR',
      confidence_score: 0.65,
      validation_outcome: 'needs_review',
      original_source_url: 'https://example.com/events/salem-ai-2026',
      additional_source_urls: ['https://mirror.com/events/salem-ai'],
      discovered_at: '2026-11-20T08:00:00Z',
      extracted_at: '2026-11-20T08:05:00Z',
      verified_at: null,
      update_history: [
        {
          timestamp: '2026-11-20T09:30:00Z',
          source_url: 'https://mirror.com/events/salem-ai',
          changes: {
            venue_name: {
              old: 'Salem Tech Campus',
              new: 'Salem Engineering College',
            },
          },
        },
      ],
    }

    vi.spyOn(api, 'getAdminReviewQueue').mockResolvedValue([mockReviewEvent])
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getByText(/Review Queue/i)).toBeDefined()
    })

    fireEvent.click(screen.getByText(/Review Queue/i))

    await waitFor(() => {
      expect(screen.getByText('Salem AI Symposium 2026')).toBeDefined()
      expect(screen.getByText(/Evidence Drawer/i)).toBeDefined()
    })

    // Click Evidence Drawer button
    fireEvent.click(screen.getByText(/Evidence Drawer/i))

    await waitFor(() => {
      expect(screen.getByText(/Evidence Drawer: Salem AI Symposium 2026/i)).toBeDefined()
      expect(screen.getByText('https://example.com/events/salem-ai-2026')).toBeDefined()
      expect(screen.getByText('https://mirror.com/events/salem-ai')).toBeDefined()
      expect(screen.getByText(/Salem Engineering College/i)).toBeDefined()
    })
  })
})
