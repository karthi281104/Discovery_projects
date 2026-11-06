import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { DiscoveryMonitor } from './DiscoveryMonitor'
import {
  adminLogin,
  createAdminCategory,
  createAdminEvent,
  createAdminLocation,
  deactivateAdminCategory,
  deleteAdminCategory,
  deleteAdminEvent,
  deleteAdminLocation,
  getAdminCategories,
  getAdminEvent,
  getAdminEvents,
  getAdminLocations,
  getAdminMetrics,
  updateAdminEvent,
  updateEventAction,
} from './api'
import type { AdminMetrics, Category, EventList, EventMode, EventStatus, EventType, Location } from './types'

export function AdminLogin() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await adminLogin(email, password)
      localStorage.setItem('admin_token', result.access_token)
      navigate('/admin/dashboard')
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page-shell content-page admin-auth">
      <div className="auth-card">
        <p className="eyebrow">ADMINISTRATION</p>
        <h1>Welcome back.</h1>
        <form onSubmit={submit}>
          <label>
            Email
            <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="error-state">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </main>
  )
}

function RedirectToLogin() {
  const navigate = useNavigate()
  useEffect(() => {
    navigate('/admin/login')
  }, [navigate])
  return null
}

export function AdminDashboard() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'events' | 'categories' | 'locations' | 'discovery'>('events')
  const [events, setEvents] = useState<EventList | null>(null)
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Event filters
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [modeFilter, setModeFilter] = useState('')
  const [page, setPage] = useState(1)

  // New Category form state
  const [newCatName, setNewCatName] = useState('')
  const [newCatDesc, setNewCatDesc] = useState('')

  // New Location form state
  const [newLocName, setNewLocName] = useState('')
  const [newLocCity, setNewLocCity] = useState('')
  const [newLocDistrict, setNewLocDistrict] = useState('')

  const token = localStorage.getItem('admin_token')
  if (!token) return <RedirectToLogin />

  const loadData = () => {
    setLoading(true)
    Promise.all([
      getAdminMetrics().then(setMetrics).catch(() => null),
      getAdminEvents({
        page,
        page_size: 20,
        search: search || undefined,
        status: statusFilter || undefined,
        category_id: categoryFilter || undefined,
        mode: modeFilter || undefined,
      }).then(setEvents),
      getAdminCategories().then(setCategories).catch(() => []),
      getAdminLocations().then(setLocations).catch(() => []),
    ])
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [page, statusFilter, categoryFilter, modeFilter])

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault()
    setPage(1)
    loadData()
  }

  const handleAction = async (id: number | string, operation: 'publish' | 'reject' | 'feature' | 'unfeature') => {
    try {
      await updateEventAction(id, operation)
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleDeleteEvent = async (id: number | string, title: string) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"? This action cannot be undone.`)) {
      return
    }
    try {
      await deleteAdminEvent(id)
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleCreateCategory = async (e: FormEvent) => {
    e.preventDefault()
    if (!newCatName.trim()) return
    try {
      await createAdminCategory({ name: newCatName.trim(), description: newCatDesc.trim() || undefined })
      setNewCatName('')
      setNewCatDesc('')
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleToggleCategoryActive = async (id: number | string) => {
    try {
      await deactivateAdminCategory(id)
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleDeleteCategory = async (id: number | string, name: string) => {
    if (!window.confirm(`Delete category "${name}"?`)) return
    try {
      await deleteAdminCategory(id)
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleCreateLocation = async (e: FormEvent) => {
    e.preventDefault()
    if (!newLocName.trim() || !newLocCity.trim()) return
    try {
      await createAdminLocation({
        name: newLocName.trim(),
        city: newLocCity.trim(),
        district: newLocDistrict.trim() || undefined,
        state: 'Tamil Nadu',
      })
      setNewLocName('')
      setNewLocCity('')
      setNewLocDistrict('')
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  const handleDeleteLocation = async (id: number | string, name: string) => {
    if (!window.confirm(`Delete location "${name}"?`)) return
    try {
      await deleteAdminLocation(id)
      loadData()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  return (
    <main className="page-shell content-page admin-page">
      <div className="section-heading">
        <div>
          <p className="eyebrow">CONTROL CENTER</p>
          <h1>Event Dashboard</h1>
        </div>
        <div>
          <Link className="primary-button" to="/admin/events/new">
            + Create event
          </Link>{' '}
          <button
            onClick={() => {
              localStorage.removeItem('admin_token')
              navigate('/admin/login')
            }}
          >
            Sign out
          </button>
        </div>
      </div>

      {error && <div className="error-state">{error}</div>}

      <div className="metric-grid">
        <div className="metric-card">
          <span>Total events</span>
          <strong>{metrics?.total_events ?? events?.total ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Published</span>
          <strong>{metrics?.published_events ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Drafts</span>
          <strong>{metrics?.draft_events ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Pending</span>
          <strong>{metrics?.pending_events ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Featured</span>
          <strong>{metrics?.featured_events ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Categories</span>
          <strong>{metrics?.total_categories ?? categories.length}</strong>
        </div>
        <div className="metric-card">
          <span>Locations</span>
          <strong>{metrics?.total_locations ?? locations.length}</strong>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid #333', marginBottom: '1.5rem', paddingBottom: '0.5rem' }}>
        <button
          style={{ fontWeight: activeTab === 'events' ? 'bold' : 'normal', background: 'none', border: 'none', color: activeTab === 'events' ? '#fff' : '#888', cursor: 'pointer', fontSize: '1rem' }}
          onClick={() => setActiveTab('events')}
        >
          Events ({events?.total ?? 0})
        </button>
        <button
          style={{ fontWeight: activeTab === 'categories' ? 'bold' : 'normal', background: 'none', border: 'none', color: activeTab === 'categories' ? '#fff' : '#888', cursor: 'pointer', fontSize: '1rem' }}
          onClick={() => setActiveTab('categories')}
        >
          Categories ({categories.length})
        </button>
        <button
          style={{ fontWeight: activeTab === 'locations' ? 'bold' : 'normal', background: 'none', border: 'none', color: activeTab === 'locations' ? '#fff' : '#888', cursor: 'pointer', fontSize: '1rem' }}
          onClick={() => setActiveTab('locations')}
        >
          Locations ({locations.length})
        </button>
        <button
          style={{ fontWeight: activeTab === 'discovery' ? 'bold' : 'normal', background: 'none', border: 'none', color: activeTab === 'discovery' ? '#fff' : '#888', cursor: 'pointer', fontSize: '1rem' }}
          onClick={() => setActiveTab('discovery')}
        >
          Discovery Monitor
        </button>
      </div>

      {activeTab === 'events' && (
        <>
          <div className="filters" style={{ marginBottom: '1.5rem' }}>
            <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.5rem', flex: 1 }}>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search events or organizers..."
                aria-label="Search events"
              />
              <button type="submit">Search</button>
            </form>
            <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}>
              <option value="">All statuses</option>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="pending">Pending</option>
              <option value="rejected">Rejected</option>
              <option value="cancelled">Cancelled</option>
              <option value="expired">Expired</option>
            </select>
            <select value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setPage(1) }}>
              <option value="">All categories</option>
              {categories.map((cat) => (
                <option value={cat.id} key={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
            <select value={modeFilter} onChange={(e) => { setModeFilter(e.target.value); setPage(1) }}>
              <option value="">All modes</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </div>

          <div className="admin-table">
            <div className="table-row table-head">
              <span>Event</span>
              <span>Details</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {loading ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>Loading events...</div>
            ) : !events?.items.length ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>No events found matching your criteria.</div>
            ) : (
              events.items.map((event) => (
                <div className="table-row" key={event.id}>
                  <span>
                    <strong>{event.title}</strong>
                    <br />
                    <small>{event.organizer_name} • {event.city || 'Online'}</small>
                  </span>
                  <span>
                    <small>{event.category?.name || event.event_type} • {event.mode}</small>
                    <br />
                    <small>◷ {new Date(event.start_date).toLocaleDateString('en-IN')}</small>
                  </span>
                  <span>
                    <span className={`status-${event.status}`}>{event.status}</span>
                    {event.is_featured && <span style={{ marginLeft: '0.4rem', fontSize: '0.75rem', background: '#ffd700', color: '#000', padding: '2px 6px', borderRadius: '4px' }}>Featured</span>}
                  </span>
                  <span className="table-actions">
                    <Link className="text-link" to={`/admin/events/${event.id}/edit`} style={{ marginRight: '0.5rem' }}>
                      Edit
                    </Link>
                    {event.status !== 'published' && (
                      <button onClick={() => handleAction(event.id, 'publish')}>Publish</button>
                    )}
                    {event.status !== 'rejected' && (
                      <button onClick={() => handleAction(event.id, 'reject')}>Reject</button>
                    )}
                    <button onClick={() => handleAction(event.id, event.is_featured ? 'unfeature' : 'feature')}>
                      {event.is_featured ? 'Unfeature' : 'Feature'}
                    </button>
                    <button onClick={() => handleDeleteEvent(event.id, event.title)} style={{ color: '#ff6b6b' }}>
                      Delete
                    </button>
                  </span>
                </div>
              ))
            )}
          </div>

          {events && events.pages > 1 && (
            <div className="pagination" style={{ marginTop: '1.5rem' }}>
              <button disabled={events.page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </button>
              <span>Page {events.page} of {events.pages}</span>
              <button disabled={events.page >= events.pages} onClick={() => setPage((p) => Math.min(events.pages, p + 1))}>
                Next
              </button>
            </div>
          )}
        </>
      )}

      {activeTab === 'categories' && (
        <div>
          <div style={{ background: '#1c1c1e', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem' }}>
            <h3>Add New Category</h3>
            <form onSubmit={handleCreateCategory} style={{ display: 'flex', gap: '0.8rem', marginTop: '0.8rem' }}>
              <input
                required
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="Category name (e.g. Technology & Hackathons)"
                style={{ flex: 1 }}
              />
              <input
                value={newCatDesc}
                onChange={(e) => setNewCatDesc(e.target.value)}
                placeholder="Description"
                style={{ flex: 2 }}
              />
              <button type="submit">+ Add Category</button>
            </form>
          </div>

          <div className="admin-table">
            <div className="table-row table-head">
              <span>Category</span>
              <span>Slug</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {categories.map((cat) => (
              <div className="table-row" key={cat.id}>
                <span>
                  <strong>{cat.name}</strong>
                  <br />
                  <small>{cat.description || 'No description'}</small>
                </span>
                <span><code>{cat.slug}</code></span>
                <span>
                  <span style={{ color: cat.is_active !== false ? '#4cd964' : '#ff3b30' }}>
                    {cat.is_active !== false ? 'Active' : 'Inactive'}
                  </span>
                </span>
                <span className="table-actions">
                  <button onClick={() => handleToggleCategoryActive(cat.id)}>
                    {cat.is_active !== false ? 'Deactivate' : 'Activate'}
                  </button>
                  <button onClick={() => handleDeleteCategory(cat.id, cat.name)} style={{ color: '#ff6b6b' }}>
                    Delete
                  </button>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'locations' && (
        <div>
          <div style={{ background: '#1c1c1e', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem' }}>
            <h3>Add New Location</h3>
            <form onSubmit={handleCreateLocation} style={{ display: 'flex', gap: '0.8rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
              <input
                required
                value={newLocName}
                onChange={(e) => setNewLocName(e.target.value)}
                placeholder="Venue / Name"
                style={{ flex: 1, minWidth: '200px' }}
              />
              <input
                required
                value={newLocCity}
                onChange={(e) => setNewLocCity(e.target.value)}
                placeholder="City"
                style={{ flex: 1, minWidth: '150px' }}
              />
              <input
                value={newLocDistrict}
                onChange={(e) => setNewLocDistrict(e.target.value)}
                placeholder="District (optional)"
                style={{ flex: 1, minWidth: '150px' }}
              />
              <button type="submit">+ Add Location</button>
            </form>
          </div>

          <div className="admin-table">
            <div className="table-row table-head">
              <span>Location / Venue</span>
              <span>City</span>
              <span>District / State</span>
              <span>Actions</span>
            </div>
            {locations.map((loc) => (
              <div className="table-row" key={loc.id}>
                <span><strong>{loc.name}</strong></span>
                <span>{loc.city}</span>
                <span>{loc.district ? `${loc.district}, ` : ''}{loc.state}</span>
                <span className="table-actions">
                  <button onClick={() => handleDeleteLocation(loc.id, loc.name)} style={{ color: '#ff6b6b' }}>
                    Delete
                  </button>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'discovery' && <DiscoveryMonitor />}
    </main>
  )
}

const initialForm = {
  title: '',
  slug: '',
  short_description: '',
  description: '',
  organizer_name: '',
  organizer_website: '',
  category_id: '' as string | number,
  event_type: 'other' as EventType,
  mode: 'offline' as EventMode,
  start_date: '',
  end_date: '',
  registration_deadline: '',
  registration_url: '',
  official_website: '',
  banner_url: '',
  contact_email: '',
  state: 'Tamil Nadu',
  district: '',
  city: '',
  venue: '',
  eligibility: '',
  participation_fee: '' as string | number,
  currency: 'INR',
  tags: '',
  status: 'draft' as EventStatus,
  is_featured: false,
}

export function AdminEventForm({ eventId: propId }: { eventId?: string | number } = {}) {
  const { id: paramId } = useParams<{ id: string }>()
  const eventId = propId || paramId
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [categories, setCategories] = useState<Category[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const token = localStorage.getItem('admin_token')
  if (!token) return <RedirectToLogin />

  useEffect(() => {
    getAdminCategories().then(setCategories).catch(() => [])

    if (eventId) {
      setLoading(true)
      getAdminEvent(eventId)
        .then((data) => {
          setForm({
            title: data.title || '',
            slug: data.slug || '',
            short_description: data.short_description || '',
            description: data.description || '',
            organizer_name: data.organizer_name || '',
            organizer_website: data.organizer_website || '',
            category_id: data.category_id || '',
            event_type: data.event_type || 'other',
            mode: data.mode || 'offline',
            start_date: data.start_date ? data.start_date.slice(0, 16) : '',
            end_date: data.end_date ? data.end_date.slice(0, 16) : '',
            registration_deadline: data.registration_deadline ? data.registration_deadline.slice(0, 16) : '',
            registration_url: data.registration_url || '',
            official_website: data.official_website || '',
            banner_url: data.banner_url || '',
            contact_email: data.contact_email || '',
            state: data.state || 'Tamil Nadu',
            district: data.district || '',
            city: data.city || '',
            venue: data.venue || '',
            eligibility: data.eligibility || '',
            participation_fee: data.participation_fee !== null && data.participation_fee !== undefined ? data.participation_fee : '',
            currency: data.currency || 'INR',
            tags: (data.tags || []).join(', '),
            status: data.status || 'draft',
            is_featured: Boolean(data.is_featured),
          })
        })
        .catch((err: Error) => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [eventId])

  const set = (key: string, value: unknown) => setForm((cur) => ({ ...cur, [key]: value }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (form.end_date && form.start_date && form.start_date > form.end_date) {
      setError('End date must not be earlier than start date.')
      return
    }

    if (!form.registration_url.startsWith('http://') && !form.registration_url.startsWith('https://')) {
      setError('Registration URL must start with http:// or https://')
      return
    }

    setSubmitting(true)
    const payload = {
      title: form.title.trim(),
      slug: form.slug.trim() || undefined,
      short_description: form.short_description.trim() || null,
      description: form.description.trim(),
      organizer_name: form.organizer_name.trim(),
      organizer_website: form.organizer_website.trim() || null,
      category_id: form.category_id ? Number(form.category_id) : null,
      event_type: form.event_type,
      mode: form.mode,
      start_date: form.start_date,
      end_date: form.end_date || null,
      registration_deadline: form.registration_deadline || null,
      registration_url: form.registration_url.trim(),
      official_website: form.official_website.trim() || null,
      banner_url: form.banner_url.trim() || null,
      contact_email: form.contact_email.trim() || null,
      state: form.state.trim() || 'Tamil Nadu',
      district: form.district.trim() || null,
      city: form.city.trim() || null,
      venue: form.venue.trim() || null,
      eligibility: form.eligibility.trim() || null,
      participation_fee: form.participation_fee !== '' ? Number(form.participation_fee) : null,
      currency: form.currency || 'INR',
      tags: form.tags
        ? form.tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
        : [],
      status: form.status,
      is_featured: form.is_featured,
    }

    try {
      if (eventId) {
        await updateAdminEvent(eventId, payload)
      } else {
        await createAdminEvent(payload)
      }
      navigate('/admin/dashboard')
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <main className="page-shell content-page admin-page">
        <div style={{ padding: '2rem' }}>Loading event details...</div>
      </main>
    )
  }

  return (
    <main className="page-shell content-page admin-page">
      <Link className="text-link" to="/admin/dashboard">
        ← Back to dashboard
      </Link>
      <h1>{eventId ? 'Edit Event' : 'Create Event'}</h1>

      <form className="event-form" onSubmit={submit}>
        <label>
          Title *
          <input required value={form.title} onChange={(e) => set('title', e.target.value)} />
        </label>

        <label>
          Slug (optional, generated automatically if blank)
          <input value={form.slug} onChange={(e) => set('slug', e.target.value)} placeholder="e.g. chennai-tech-summit-2026" />
        </label>

        <label>
          Organizer Name *
          <input required value={form.organizer_name} onChange={(e) => set('organizer_name', e.target.value)} />
        </label>

        <label>
          Organizer Website
          <input type="url" value={form.organizer_website} onChange={(e) => set('organizer_website', e.target.value)} placeholder="https://..." />
        </label>

        <label>
          Category
          <select value={form.category_id} onChange={(e) => set('category_id', e.target.value)}>
            <option value="">Select category</option>
            {categories.map((cat) => (
              <option value={cat.id} key={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Event Type
          <select value={form.event_type} onChange={(e) => set('event_type', e.target.value)}>
            {[
              'hackathon',
              'conference',
              'workshop',
              'webinar',
              'competition',
              'symposium',
              'open_source',
              'startup',
              'research',
              'other',
            ].map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        <label>
          Mode
          <select value={form.mode} onChange={(e) => set('mode', e.target.value)}>
            <option value="offline">Offline</option>
            <option value="online">Online</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>

        <label>
          Start Date & Time *
          <input required type="datetime-local" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} />
        </label>

        <label>
          End Date & Time
          <input type="datetime-local" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} />
        </label>

        <label>
          Registration Deadline
          <input type="datetime-local" value={form.registration_deadline} onChange={(e) => set('registration_deadline', e.target.value)} />
        </label>

        <label>
          Registration URL *
          <input required type="url" value={form.registration_url} onChange={(e) => set('registration_url', e.target.value)} placeholder="https://..." />
        </label>

        <label>
          Official Website
          <input type="url" value={form.official_website} onChange={(e) => set('official_website', e.target.value)} placeholder="https://..." />
        </label>

        <label>
          Banner Image URL
          <input type="url" value={form.banner_url} onChange={(e) => set('banner_url', e.target.value)} placeholder="https://..." />
        </label>

        <label>
          Contact Email
          <input type="email" value={form.contact_email} onChange={(e) => set('contact_email', e.target.value)} />
        </label>

        <label>
          Short Description (summary for preview cards)
          <textarea rows={2} value={form.short_description} onChange={(e) => set('short_description', e.target.value)} />
        </label>

        <label>
          Full Description *
          <textarea required rows={7} value={form.description} onChange={(e) => set('description', e.target.value)} />
        </label>

        <label>
          City
          <input value={form.city} onChange={(e) => set('city', e.target.value)} placeholder="e.g. Chennai, Coimbatore, Madurai" />
        </label>

        <label>
          District
          <input value={form.district} onChange={(e) => set('district', e.target.value)} placeholder="e.g. Chennai, Coimbatore" />
        </label>

        <label>
          Venue
          <input value={form.venue} onChange={(e) => set('venue', e.target.value)} placeholder="e.g. Chennai Trade Centre" />
        </label>

        <label>
          Eligibility
          <textarea rows={2} value={form.eligibility} onChange={(e) => set('eligibility', e.target.value)} placeholder="e.g. Open to all college students in Tamil Nadu" />
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
          <label>
            Participation Fee (0 for free)
            <input
              type="number"
              min="0"
              step="any"
              value={form.participation_fee}
              onChange={(e) => set('participation_fee', e.target.value)}
              placeholder="0"
            />
          </label>
          <label>
            Currency
            <input value={form.currency} onChange={(e) => set('currency', e.target.value)} placeholder="INR" />
          </label>
        </div>

        <label>
          Tags (comma separated)
          <input
            value={form.tags}
            onChange={(e) => set('tags', e.target.value)}
            placeholder="AI, Web3, Hackathon, Open Source"
          />
        </label>

        <label>
          Status
          <select value={form.status} onChange={(e) => set('status', e.target.value)}>
            <option value="draft">Draft</option>
            <option value="pending">Pending</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
            <option value="cancelled">Cancelled</option>
            <option value="expired">Expired</option>
          </select>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={form.is_featured}
            onChange={(e) => set('is_featured', e.target.checked)}
            style={{ width: 'auto' }}
          />
          Feature this event on the home page
        </label>

        {error && <div className="error-state">{error}</div>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : eventId ? 'Update Event' : 'Create Event'}
        </button>
      </form>
    </main>
  )
}
