import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EventCard, EventGrid } from '../components'
import type { Event } from '../types'

const mockEvent: Event = {
  id: 1,
  title: 'Tamil Nadu Developer Summit',
  slug: 'tamil-nadu-developer-summit',
  short_description: 'Connecting technologists from across Tamil Nadu.',
  description: 'Detailed description of the summit with workshops and technical tracks.',
  organizer_name: 'TN Developers Council',
  event_type: 'conference',
  mode: 'hybrid',
  start_date: '2026-11-20T09:00:00Z',
  end_date: '2026-11-21T17:00:00Z',
  registration_url: 'https://example.com/register',
  state: 'Tamil Nadu',
  city: 'Chennai',
  venue: 'Chennai Trade Centre',
  participation_fee: 500,
  currency: 'INR',
  tags: ['Tech', 'Summit'],
  status: 'published',
  is_published: true,
  is_featured: true,
}

describe('EventCard component', () => {
  it('renders event title, organizer, and details accurately', () => {
    render(<EventCard event={mockEvent} />)
    expect(screen.getByText('Tamil Nadu Developer Summit')).toBeDefined()
    expect(screen.getByText('Connecting technologists from across Tamil Nadu.')).toBeDefined()
    expect(screen.getByText(/Chennai Trade Centre, Chennai/)).toBeDefined()
    expect(screen.getByText(/hybrid/i)).toBeDefined()
    expect(screen.getByText('View details →')).toBeDefined()
  })

  it('renders online mode properly when mode is online', () => {
    const onlineEvent: Event = { ...mockEvent, mode: 'online', city: null, venue: null }
    render(<EventCard event={onlineEvent} />)
    expect(screen.getByText(/Online/)).toBeDefined()
  })
})

describe('EventGrid component', () => {
  it('renders a list of events', () => {
    render(<EventGrid events={[mockEvent]} />)
    expect(screen.getByText('Tamil Nadu Developer Summit')).toBeDefined()
  })

  it('renders empty message when no events are provided', () => {
    render(<EventGrid events={[]} empty="No upcoming opportunities." />)
    expect(screen.getByText('No upcoming opportunities.')).toBeDefined()
  })
})

