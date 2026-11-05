import { FormEvent, useEffect, useState } from 'react'
import { adminLogin, createAdminEvent, deleteAdminEvent, getAdminEvents, updateEventAction } from './api'
import type { EventList, EventMode, EventType } from './types'

export function AdminLogin() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try { const result = await adminLogin(email, password); localStorage.setItem('admin_token', result.access_token); window.location.href = '/admin/dashboard' } catch (reason) { setError((reason as Error).message) }
  }
  return <main className="page-shell content-page admin-auth"><div className="auth-card"><p className="eyebrow">ADMINISTRATION</p><h1>Welcome back.</h1><form onSubmit={submit}><label>Email<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <div className="error-state">{error}</div>}<button type="submit">Sign in</button></form></div></main>
}

export function AdminDashboard() {
  const [events, setEvents] = useState<EventList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = () => getAdminEvents({ page_size: 100 }).then(setEvents).catch((reason: Error) => setError(reason.message))
  useEffect(() => { load() }, [])
  if (!localStorage.getItem('admin_token')) return <RedirectToLogin />
  const action = async (id: string, operation: 'publish' | 'reject' | 'feature') => { try { await updateEventAction(id, operation); load() } catch (reason) { setError((reason as Error).message) } }
  return <main className="page-shell content-page admin-page"><div className="section-heading"><div><p className="eyebrow">CONTROL CENTER</p><h1>Event dashboard</h1></div><div><a className="primary-button" href="/admin/events/new">Create event</a> <button onClick={() => { localStorage.removeItem('admin_token'); window.location.href = '/admin/login' }}>Sign out</button></div></div>{error && <div className="error-state">{error}</div>}<div className="metric-grid">{['Total events', 'Published', 'Drafts', 'Pending'].map((label, index) => <div className="metric-card" key={label}><span>{label}</span><strong>{index === 0 ? events?.total ?? 0 : events?.items.filter((event) => event.status === ['published', 'published', 'draft', 'pending'][index]).length ?? 0}</strong></div>)}</div><div className="admin-table"><div className="table-row table-head"><span>Event</span><span>Status</span><span>Actions</span></div>{events?.items.map((event) => <div className="table-row" key={event.id}><span><strong>{event.title}</strong><small>{event.organizer_name}</small></span><span className={`status-${event.status}`}>{event.status}</span><span className="table-actions">{event.status !== 'published' && <button onClick={() => action(event.id, 'publish')}>Publish</button>}<button onClick={() => action(event.id, 'feature')}>{event.is_featured ? 'Unfeature' : 'Feature'}</button><button onClick={() => deleteAdminEvent(event.id).then(load).catch((reason: Error) => setError(reason.message))}>Delete</button></span></div>)}</div></main>
}

function RedirectToLogin() { useEffect(() => { window.location.href = '/admin/login' }, []); return null }

const initialForm = { title: '', description: '', short_description: '', organizer_name: '', event_type: 'other' as EventType, mode: 'online' as EventMode, start_date: '', end_date: '', registration_url: '', state: 'Tamil Nadu', city: '', status: 'draft' as const, is_featured: false, tags: [] as string[] }
export function AdminEventForm() {
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState<string | null>(null)
  const set = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }))
  const submit = async (event: FormEvent) => { event.preventDefault(); if (form.end_date && form.start_date > form.end_date) { setError('End date must not be earlier than start date.'); return } try { await createAdminEvent(form); window.location.href = '/admin/dashboard' } catch (reason) { setError((reason as Error).message) } }
  return <main className="page-shell content-page admin-page"><a className="text-link" href="/admin/dashboard">← Dashboard</a><h1>Create event</h1><form className="event-form" onSubmit={submit}><label>Title *<input required value={form.title} onChange={(e) => set('title', e.target.value)} /></label><label>Organizer *<input required value={form.organizer_name} onChange={(e) => set('organizer_name', e.target.value)} /></label><label>Short description<textarea value={form.short_description} onChange={(e) => set('short_description', e.target.value)} /></label><label>Description *<textarea required rows={7} value={form.description} onChange={(e) => set('description', e.target.value)} /></label><label>Event type<select value={form.event_type} onChange={(e) => set('event_type', e.target.value)}>{['hackathon', 'conference', 'workshop', 'webinar', 'competition', 'symposium', 'open_source', 'startup', 'research', 'other'].map((type) => <option key={type}>{type}</option>)}</select></label><label>Mode<select value={form.mode} onChange={(e) => set('mode', e.target.value)}><option>online</option><option>offline</option><option>hybrid</option></select></label><label>Start date *<input required type="datetime-local" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} /></label><label>End date *<input required type="datetime-local" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} /></label><label>Registration URL *<input required type="url" value={form.registration_url} onChange={(e) => set('registration_url', e.target.value)} /></label><label>City<input value={form.city} onChange={(e) => set('city', e.target.value)} /></label>{error && <div className="error-state">{error}</div>}<button type="submit">Create draft</button></form></main>
}
