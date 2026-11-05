import { FormEvent, useEffect, useState } from 'react'
import { getCategories, getEvent, getEvents, getFeaturedEvents, getLocations, getUpcomingEvents } from './api'
import { EventGrid } from './components'
import type { Category, Event, EventList, Location } from './types'

export function HomePage() {
  const [featured, setFeatured] = useState<Event[]>([])
  const [upcoming, setUpcoming] = useState<Event[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getFeaturedEvents(), getUpcomingEvents(), getCategories()])
      .then(([featuredEvents, upcomingEvents, categoryList]) => {
        setFeatured(featuredEvents)
        setUpcoming(upcomingEvents)
        setCategories(categoryList)
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="page-shell">
      <section className="hero hero-home">
        <p className="eyebrow">YOUR NEXT OPPORTUNITY STARTS HERE</p>
        <h1>
          Find events.<br />
          <span>Find your next big thing.</span>
        </h1>
        <p className="hero-copy">
          Discover hackathons, workshops, conferences, competitions and more across Tamil Nadu.
        </p>
        <SearchForm />
      </section>

      {error ? (
        <div className="error-state">{error}</div>
      ) : loading ? (
        <div className="loading-state">Loading opportunities...</div>
      ) : (
        <>
          <section className="content-section">
            <SectionHeading title="Featured events" link="/events?featured=true" />
            <EventGrid events={featured} empty="No featured events found at the moment." />
          </section>
          <section className="content-section">
            <SectionHeading title="Upcoming opportunities" link="/events?time=upcoming" />
            <EventGrid events={upcoming} empty="No upcoming events scheduled right now." />
          </section>
          <section className="content-section">
            <SectionHeading title="Browse by category" />
            <div className="category-grid">
              {categories.map((category) => (
                <a className="category-card" href={`/events?category=${category.slug}`} key={category.id}>
                  <strong>{category.icon || '✦'}</strong>
                  <span>{category.name}</span>
                </a>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  )
}

function SearchForm() {
  const [query, setQuery] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    window.location.href = `/events${query ? `?search=${encodeURIComponent(query)}` : ''}`
  }
  return (
    <form className="search-form" onSubmit={submit}>
      <span className="search-icon">⌕</span>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search events, topics or organizers"
        aria-label="Search events"
      />
      <button type="submit">Search</button>
    </form>
  )
}

function SectionHeading({ title, link }: { title: string; link?: string }) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {link && (
        <a className="text-link" href={link}>
          View all →
        </a>
      )}
    </div>
  )
}

export function ExplorePage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [result, setResult] = useState<EventList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const initial = new URLSearchParams(window.location.search)
  const [filters, setFilters] = useState({
    search: initial.get('search') || '',
    category: initial.get('category') || '',
    city: initial.get('city') || '',
    mode: initial.get('mode') || '',
    time: initial.get('time') || '',
    featured: initial.get('featured') || '',
    sort: initial.get('sort') || 'start_date',
    page: initial.get('page') || '1',
  })

  useEffect(() => {
    Promise.all([getCategories(), getLocations()])
      .then(([cats, cities]) => {
        setCategories(cats)
        setLocations(cities)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [])

  useEffect(() => {
    setLoading(true)
    getEvents(filters)
      .then(setResult)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [filters])

  const change = (key: string, value: string) =>
    setFilters((current) => ({
      ...current,
      [key]: value,
      page: key === 'page' ? value : '1',
    }))

  // Unique cities list for the dropdown
  const uniqueCities = Array.from(new Set(locations.map((loc) => loc.city))).filter(Boolean)

  return (
    <main className="page-shell content-page">
      <div className="page-intro">
        <p className="eyebrow">EXPLORE OPPORTUNITIES</p>
        <h1>Events worth showing up for.</h1>
        <p className="hero-copy">Search and filter verified opportunities across Tamil Nadu.</p>
      </div>

      <div className="filters">
        <input
          value={filters.search}
          onChange={(e) => change('search', e.target.value)}
          placeholder="Search events..."
          aria-label="Search events"
        />
        <select value={filters.category} onChange={(e) => change('category', e.target.value)}>
          <option value="">All categories</option>
          {categories.map((item) => (
            <option value={item.slug} key={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <select value={filters.city} onChange={(e) => change('city', e.target.value)}>
          <option value="">All cities</option>
          {uniqueCities.map((cityName) => (
            <option value={cityName} key={cityName}>
              {cityName}
            </option>
          ))}
        </select>
        <select value={filters.mode} onChange={(e) => change('mode', e.target.value)}>
          <option value="">Any mode</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="hybrid">Hybrid</option>
        </select>
        <select value={filters.time} onChange={(e) => change('time', e.target.value)}>
          <option value="">Any date</option>
          <option value="upcoming">Upcoming</option>
          <option value="ongoing">Ongoing</option>
          <option value="past">Past</option>
        </select>
        <select value={filters.sort} onChange={(e) => change('sort', e.target.value)}>
          <option value="start_date">Soonest</option>
          <option value="-start_date">Latest start</option>
          <option value="-created_at">Recently added</option>
        </select>
      </div>

      {error ? (
        <div className="error-state">{error}</div>
      ) : loading ? (
        <div className="loading-state">Loading events...</div>
      ) : result ? (
        <>
          <EventGrid events={result.items} empty="No events found matching your filter criteria." />
          {result.pages > 1 && (
            <div className="pagination">
              <button disabled={result.page <= 1} onClick={() => change('page', String(result.page - 1))}>
                Previous
              </button>
              <span>
                Page {result.page} of {result.pages}
              </span>
              <button disabled={result.page >= result.pages} onClick={() => change('page', String(result.page + 1))}>
                Next
              </button>
            </div>
          )}
        </>
      ) : null}
    </main>
  )
}

export function EventDetailsPage({ slug }: { slug: string }) {
  const [event, setEvent] = useState<Event | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getEvent(slug)
      .then(setEvent)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [slug])

  if (error) {
    return (
      <main className="page-shell content-page">
        <a className="text-link" href="/events" style={{ display: 'inline-block', marginBottom: '1rem' }}>
          ← Back to events
        </a>
        <div className="error-state">{error}</div>
      </main>
    )
  }

  if (loading || !event) {
    return (
      <main className="page-shell content-page">
        <div className="loading-state">Loading event details...</div>
      </main>
    )
  }

  const tagsList = event.tags || []
  const hasFee = event.participation_fee !== null && event.participation_fee !== undefined

  return (
    <main className="page-shell content-page event-detail">
      <a className="text-link" href="/events">
        ← Back to events
      </a>
      <div className="detail-header">
        {event.banner_url && <img src={event.banner_url} alt="" />}
        <div>
          <div className="card-meta">
            <span>{event.category?.name ?? event.event_type}</span>
            <span>{event.mode}</span>
          </div>
          <h1>{event.title}</h1>
          {event.short_description && <p className="hero-copy">{event.short_description}</p>}
        </div>
      </div>
      <div className="detail-layout">
        <article>
          <h2>About this event</h2>
          <p className="detail-description">{event.description}</p>
          {event.eligibility && (
            <>
              <h2>Eligibility</h2>
              <p>{event.eligibility}</p>
            </>
          )}
          {tagsList.length > 0 && (
            <div className="tag-row">
              {tagsList.map((tag) => (
                <span className="category-chip" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          )}
        </article>
        <aside className="detail-aside">
          <strong>{event.organizer_name}</strong>
          {event.organizer_website && (
            <p>
              <a href={event.organizer_website} target="_blank" rel="noopener noreferrer" className="text-link">
                Organizer Website ↗
              </a>
            </p>
          )}
          <p>◷ {new Date(event.start_date).toLocaleString('en-IN')}</p>
          {event.end_date && (
            <p>Ends: {new Date(event.end_date).toLocaleString('en-IN')}</p>
          )}
          <p>
            ⌖ {event.mode === 'online' ? 'Online event' : [event.venue, event.city, event.district, event.state].filter(Boolean).join(', ')}
          </p>
          {event.registration_deadline && (
            <p>Registration deadline: {new Date(event.registration_deadline).toLocaleDateString('en-IN')}</p>
          )}
          {hasFee && (
            <p>
              {event.participation_fee && event.participation_fee > 0
                ? `${event.currency || 'INR'} ${event.participation_fee}`
                : 'Free entry'}
            </p>
          )}
          {event.official_website && (
            <p>
              <a href={event.official_website} target="_blank" rel="noopener noreferrer" className="text-link">
                Official Website ↗
              </a>
            </p>
          )}
          <a className="primary-button" href={event.registration_url} target="_blank" rel="noopener noreferrer">
            Register officially ↗
          </a>
        </aside>
      </div>
    </main>
  )
}
