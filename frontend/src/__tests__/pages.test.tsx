import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { EventDetailsPage, ExplorePage } from '../pages'
import * as api from '../api'
import type { Event, EventList, Category, Location } from '../types'

const mockEvent: Event = {
  id: 1,
  title: 'Tamil Nadu Developer Summit',
  slug: 'tamil-nadu-developer-summit',
  short_description: 'Connecting technologists from across Tamil Nadu.',
  description: 'Full description of the developer summit with deep dive sessions.',
  organizer_name: 'TN Developers Council',
  organizer_website: 'https://example.com/org',
  event_type: 'conference',
  mode: 'hybrid',
  start_date: '2026-11-20T09:00:00Z',
  end_date: '2026-11-21T17:00:00Z',
  registration_deadline: '2026-11-15T23:59:00Z',
  registration_url: 'https://example.com/register',
  official_website: 'https://example.com/official',
  state: 'Tamil Nadu',
  city: 'Chennai',
  venue: 'Chennai Trade Centre',
  eligibility: 'All students and engineers',
  participation_fee: 500,
  currency: 'INR',
  tags: ['Tech', 'Summit'],
  status: 'published',
  is_published: true,
  is_featured: true,
}

const mockCategories: Category[] = [
  { id: 1, name: 'Technology & Hackathons', slug: 'technology-hackathons', is_active: true },
  { id: 2, name: 'Cultural & Arts', slug: 'cultural-arts', is_active: true },
]

const mockLocations: Location[] = [
  { id: 1, name: 'Chennai Trade Centre', city: 'Chennai', state: 'Tamil Nadu', is_active: true },
  { id: 2, name: 'CODISSIA', city: 'Coimbatore', state: 'Tamil Nadu', is_active: true },
]

const mockEventList: EventList = {
  items: [mockEvent],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}

describe('EventDetailsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders event details including fees, eligibility, and official links', async () => {
    vi.spyOn(api, 'getEvent').mockResolvedValue(mockEvent)

    render(<EventDetailsPage slug="tamil-nadu-developer-summit" />)

    // Loading state initially
    expect(screen.getByText(/Loading event details.../)).toBeDefined()

    // Wait for event data
    await waitFor(() => {
      expect(screen.getByText('Tamil Nadu Developer Summit')).toBeDefined()
    })

    expect(screen.getByText('Full description of the developer summit with deep dive sessions.')).toBeDefined()
    expect(screen.getByText('TN Developers Council')).toBeDefined()
    expect(screen.getByText('All students and engineers')).toBeDefined()
    expect(screen.getByText(/INR 500/)).toBeDefined()
    expect(screen.getByText('Register officially ↗')).toBeDefined()
  })

  it('renders error state on API failure', async () => {
    vi.spyOn(api, 'getEvent').mockRejectedValue(new Error('Event not found (404)'))

    render(<EventDetailsPage slug="unknown-event" />)

    await waitFor(() => {
      expect(screen.getByText('Event not found (404)')).toBeDefined()
    })
  })
})

describe('ExplorePage filters', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'getCategories').mockResolvedValue(mockCategories)
    vi.spyOn(api, 'getLocations').mockResolvedValue(mockLocations)
    vi.spyOn(api, 'getEvents').mockResolvedValue(mockEventList)
  })

  it('renders filters and allows changing category and search', async () => {
    render(<ExplorePage />)

    await waitFor(() => {
      expect(screen.getByText('Tamil Nadu Developer Summit')).toBeDefined()
    })

    const searchInput = screen.getByPlaceholderText('Search events...')
    fireEvent.change(searchInput, { target: { value: 'Developer' } })

    const categorySelect = screen.getByDisplayValue('All categories')
    fireEvent.change(categorySelect, { target: { value: 'technology-hackathons' } })

    await waitFor(() => {
      expect(api.getEvents).toHaveBeenCalled()
    })
  })
})

