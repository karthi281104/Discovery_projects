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
  })

  it('renders discovery metrics, sources table, and recent runs', async () => {
    render(<DiscoveryMonitor />)

    await waitFor(() => {
      expect(screen.getAllByText('KnowAFest RSS Feed')[0]).toBeDefined()
    })

    expect(screen.getByText('Active Sources')).toBeDefined()
    expect(screen.getByText('Events Auto-Created')).toBeDefined()
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
      expect(screen.getByText('Generic Event Title')).toBeDefined()
      expect(screen.getByText('Title is generic or boilerplate')).toBeDefined()
    })
  })
})
