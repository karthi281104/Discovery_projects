import type { Event } from './types'

const formatDate = (value: string) => new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(value))

export function EventCard({ event }: { event: Event }) {
  return (
    <article className="event-card">
      {event.banner_url ? <img src={event.banner_url} alt="" className="event-banner" /> : <div className="event-banner event-banner-fallback">{event.event_type.replace('_', ' ')}</div>}
      <div className="event-card-body">
        <div className="card-meta"><span>{event.category?.name ?? event.event_type}</span><span>{event.mode}</span></div>
        <h3>{event.title}</h3>
        <p className="muted">{event.short_description || event.description}</p>
        <p className="event-line">◷ {formatDate(event.start_date)}{event.end_date !== event.start_date ? ` – ${formatDate(event.end_date)}` : ''}</p>
        <p className="event-line">⌖ {event.mode === 'online' ? 'Online' : event.city || event.state}</p>
        <a className="text-link" href={`/events/${event.slug}`}>View details →</a>
      </div>
    </article>
  )
}

export function EventGrid({ events, empty = 'No events found.' }: { events: Event[]; empty?: string }) {
  if (!events.length) return <div className="empty-state">{empty}</div>
  return <div className="event-grid">{events.map((event) => <EventCard event={event} key={event.id} />)}</div>
}
