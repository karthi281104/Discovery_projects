import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { AdminLogin, AdminEventForm, AdminDashboard } from '../admin'
import * as api from '../api'
import type { Event, EventList, AdminMetrics } from '../types'

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

    render(<AdminLogin />)

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

    render(<AdminLogin />)

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
    vi.spyOn(api, 'getAdminCategories').mockResolvedValue([])
  })

  it('validates that end date cannot be earlier than start date', async () => {
    render(<AdminEventForm />)

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
    const { container } = render(<AdminEventForm />)

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
})

describe('AdminDashboard actions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('admin_token', 'valid-token')
    vi.spyOn(api, 'getAdminMetrics').mockResolvedValue(mockMetrics)
    vi.spyOn(api, 'getAdminEvents').mockResolvedValue(mockEventList)
    vi.spyOn(api, 'getAdminCategories').mockResolvedValue([])
    vi.spyOn(api, 'getAdminLocations').mockResolvedValue([])
  })

  it('renders metrics cards and event table with publish and feature buttons', async () => {
    render(<AdminDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Chennai Tech Expo')).toBeDefined()
      expect(screen.getByText('Publish')).toBeDefined()
      expect(screen.getByText('Feature')).toBeDefined()
      expect(screen.getByText('Delete')).toBeDefined()
    })
  })

  it('triggers updateEventAction on publish and feature button clicks', async () => {
    const actionSpy = vi.spyOn(api, 'updateEventAction').mockResolvedValue(mockEvent)

    render(<AdminDashboard />)

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
})
