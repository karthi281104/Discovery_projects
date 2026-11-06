import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  adminLogin,
  createAdminEvent,
  deleteAdminEvent,
  getCategories,
} from '../api'

describe('API client and header merging reliability', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('preserves Content-Type and merges Authorization header on admin write requests', async () => {
    localStorage.setItem('admin_token', 'sample-test-token')

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 10, title: 'Created Event' }),
    })
    globalThis.fetch = mockFetch

    await createAdminEvent({
      title: 'Created Event',
      description: 'Event description',
      organizer_name: 'Organizer',
      event_type: 'conference',
      mode: 'offline',
      start_date: '2026-11-20T10:00:00Z',
      registration_url: 'https://example.com/reg',
    })

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url, init] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/v1/admin/events')
    expect(init.method).toBe('POST')

    // Verify headers contain BOTH Content-Type and Authorization
    expect(init.headers).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer sample-test-token',
    })
  })

  it('preserves Content-Type on public requests without admin token', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [{ id: 1, name: 'Tech', slug: 'tech' }],
    })
    globalThis.fetch = mockFetch

    const result = await getCategories()
    expect(result).toHaveLength(1)

    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('handles 204 No Content responses cleanly as null', async () => {
    localStorage.setItem('admin_token', 'test-token')
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error('Should not call json on 204')
      },
    })
    globalThis.fetch = mockFetch

    const result = await deleteAdminEvent(99)
    expect(result).toBeNull()
  })

  it('extracts error detail string properly from API error response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Custom validation error message' }),
    })
    globalThis.fetch = mockFetch

    await expect(adminLogin('bad@example.com', 'pwd')).rejects.toThrow(
      'Custom validation error message (400)'
    )
  })

  it('falls back to default message if error response is not JSON', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('Bad gateway HTML')
      },
    })
    globalThis.fetch = mockFetch

    await expect(getCategories()).rejects.toThrow('Request failed (502)')
  })
})
