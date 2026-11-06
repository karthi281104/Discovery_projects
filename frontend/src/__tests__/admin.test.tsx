import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AdminLogin, AdminEventForm, AdminDashboard } from '../admin'
import * as api from '../api'
import type { Event, EventList, AdminMetrics, Category, Location } from '../types'

const mockEvent: Event = {
  id: 1,
  title: 'Chennai Tech Expo',
  slug: 'chennai-tech-expo',
  short_description: 'Preview summary',
  description: 'Detailed description for testing admin actions.',
  organizer_name: 'Tech Council',
  event_type: 'conference',
  mode: 'offline',
  start_date: '2026-11-20T09:00:00Z',
  end_date: '2026-11-21T17:00:00Z',
  registration_url: 'https://example.com/register',
  state: 'Tamil Nadu',
  city: 'Chennai',
  participation_fee: 0,
  currency: 'INR',
  tags: ['Tech'],
  status: 'draft',
  is_published: false,
  is_featured: false,
}

const mockMetrics: AdminMetrics = {
  total_events: 1,
  published_events: 0,
  draft_events: 1,
  pending_events: 0,
  rejected_events: 0,
  cancelled_events: 0,
  expired_events: 0,
  featured_events: 0,
  total_categories: 2,
  total_locations: 2,
}

const mockCategories: Category[] = [
  { id: 1, name: 'Tech & Hackathons', slug: 'tech-hackathons', is_active: true },
]

const mockLocations: Location[] = [
  { id: 1, name: 'Chennai Trade Centre', city: 'Chennai', state: 'Tamil Nadu', is_active: true },
]

const mockEventList: EventList = {
  items: [mockEvent],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}

describe('AdminLogin', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('renders login form and processes successful authentication', async () => {
    vi.spyOn(api, 'adminLogin').mockResolvedValue({
      access_token: 'fake-jwt-token',
      token_type: 'bearer',
    })

    render(
      <MemoryRouter>
        <AdminLogin />
      </MemoryRouter>
    )

    const emailInput = screen.getByLabelText(/Email/i)
    const passwordInput = screen.getByLabelText(/Password/i)
    const submitBtn = screen.getByRole('button', { name: /Sign in/i })

    fireEvent.change(emailInput, { target: { value: 'admin@example.com' } })
    fireEvent.change(passwordInput, { target: { value: 'password123' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(api.adminLogin).toHaveBeenCalledWith('admin@example.com', 'password123')
      expect(localStorage.getItem('admin_token')).toBe('fake-jwt-token')
    })
  })

  it('displays error message on invalid credentials', async () => {
    vi.spyOn(api, 'adminLogin').mockRejectedValue(new Error('Invalid email or password (401)'))

    render(
      <MemoryRouter>
        <AdminLogin />
      </MemoryRouter>
    )

    const emailInput = screen.getByLabelText(/Email/i)
    const passwordInput = screen.getByLabelText(/Password/i)
    const submitBtn = screen.getByRole('button', { name: /Sign in/i })

    fireEvent.change(emailInput, { target: { value: 'admin@example.com' } })
    fireEvent.change(passwordInput, { target: { value: 'wrong' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password (401)')).toBeDefined()
    })
  })
})

describe('AdminEventForm', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('admin_token', 'valid-token')
    vi.spyOn(api, 'getAdminCategories').mockResolvedValue(mockCategories)
  })

  it('validates that end date cannot be earlier than start date', async () => {
    render(
      <MemoryRouter>
        <AdminEventForm />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/Title \*/), { target: { value: 'Sample Event' } })
    fireEvent.change(screen.getByLabelText(/Organizer Name \*/), { target: { value: 'Org' } })
    fireEvent.change(screen.getByLabelText(/Description \*/), { target: { value: 'Description' } })
    fireEvent.change(screen.getByLabelText(/Registration URL \*/), { target: { value: 'https://example.com' } })
    fireEvent.change(screen.getByLabelText(/Start Date & Time \*/), { target: { value: '2026-11-20T10:00' } })
    fireEvent.change(screen.getByLabelText(/End Date & Time/), { target: { value: '2026-11-19T10:00' } })

    fireEvent.click(screen.getByRole('button', { name: /Create Event/i }))

    await waitFor(() => {
      expect(screen.getByText('End date must not be earlier than start date.')).toBeDefined()
    })
  })

  it('validates that registration URL must start with http:// or https://', async () => {
    const { container } = render(
      <MemoryRouter>
        <AdminEventForm />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/Title \*/), { target: { value: 'Sample Event' } })
    fireEvent.change(screen.getByLabelText(/Organizer Name \*/), { target: { value: 'Org' } })
    fireEvent.change(screen.getByLabelText(/Description \*/), { target: { value: 'Description' } })
    fireEvent.change(screen.getByLabelText(/Registration URL \*/), { target: { value: 'ftp://example.com' } })
    fireEvent.change(screen.getByLabelText(/Start Date & Time \*/), { target: { value: '2026-11-20T10:00' } })

    const form = container.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText('Registration URL must start with http:// or https://')).toBeDefined()
    })
  })

  it('submits update successfully when eventId is provided', async () => {
    vi.spyOn(api, 'getAdminEvent').mockResolvedValue(mockEvent)
    const updateSpy = vi.spyOn(api, 'updateAdminEvent').mockResolvedValue(mockEvent)

    const { container } = render(
      <MemoryRouter>
        <AdminEventForm eventId={1} />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(api.getAdminEvent).toHaveBeenCalledWith(1)
    })

    const titleInput = screen.getByLabelText(/Title \*/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Updated Title' } })

    const form = container.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(1, expect.objectContaining({ title: 'Updated Title' }))
    })
  })
})

describe('AdminDashboard actions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('admin_token', 'valid-token')
    vi.spyOn(api, 'getAdminMetrics').mockResolvedValue(mockMetrics)
    vi.spyOn(api, 'getAdminEvents').mockResolvedValue(mockEventList)
    vi.spyOn(api, 'getAdminCategories').mockResolvedValue(mockCategories)
    vi.spyOn(api, 'getAdminLocations').mockResolvedValue(mockLocations)
  })

  it('renders metrics cards and event table with publish, feature, and delete actions', async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Chennai Tech Expo')).toBeDefined()
      expect(screen.getByText('Publish')).toBeDefined()
      expect(screen.getByText('Feature')).toBeDefined()
      expect(screen.getByText('Delete')).toBeDefined()
    })
  })

  it('triggers updateEventAction on publish and feature button clicks', async () => {
    const actionSpy = vi.spyOn(api, 'updateEventAction').mockResolvedValue(mockEvent)

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Publish')).toBeDefined()
    })

    fireEvent.click(screen.getByText('Publish'))
    await waitFor(() => {
      expect(actionSpy).toHaveBeenCalledWith(1, 'publish')
    })

    fireEvent.click(screen.getByText('Feature'))
    await waitFor(() => {
      expect(actionSpy).toHaveBeenCalledWith(1, 'feature')
    })
  })

  it('triggers deleteAdminEvent when delete confirmed', async () => {
    window.confirm = vi.fn().mockReturnValue(true)
    const deleteSpy = vi.spyOn(api, 'deleteAdminEvent').mockResolvedValue()

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeDefined()
    })

    fireEvent.click(screen.getByText('Delete'))
    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(1)
    })
  })

  it('switches tabs and allows adding a category and location', async () => {
    const createCatSpy = vi.spyOn(api, 'createAdminCategory').mockResolvedValue({ id: 2, name: 'New Cat', slug: 'new-cat' })
    const createLocSpy = vi.spyOn(api, 'createAdminLocation').mockResolvedValue({ id: 2, name: 'New Loc', city: 'Madurai', state: 'Tamil Nadu' })

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>
    )

    // Switch to Categories tab
    fireEvent.click(screen.getByRole('button', { name: /Categories/i }))
    expect(screen.getByText('Add New Category')).toBeDefined()

    const catNameInput = screen.getByPlaceholderText(/Category name/i)
    fireEvent.change(catNameInput, { target: { value: 'New Cat' } })
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Category/i }))

    await waitFor(() => {
      expect(createCatSpy).toHaveBeenCalledWith({ name: 'New Cat', description: undefined })
    })

    // Switch to Locations tab
    fireEvent.click(screen.getByRole('button', { name: /Locations/i }))
    expect(screen.getByText('Add New Location')).toBeDefined()

    const locNameInput = screen.getByPlaceholderText(/Venue \/ Name/i)
    const locCityInput = screen.getByPlaceholderText(/^City$/i)
    fireEvent.change(locNameInput, { target: { value: 'New Loc' } })
    fireEvent.change(locCityInput, { target: { value: 'Madurai' } })
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Location/i }))

    await waitFor(() => {
      expect(createLocSpy).toHaveBeenCalledWith({
        name: 'New Loc',
        city: 'Madurai',
        district: undefined,
        state: 'Tamil Nadu',
      })
    })
  })
})
