import { useState } from 'react'
import { HomePage, ExplorePage, EventDetailsPage } from './pages'
import { AdminDashboard, AdminEventForm, AdminLogin } from './admin'

export default function App() {
  const [path] = useState(window.location.pathname)
  const eventMatch = path.match(/^\/events\/([^/]+)$/)
  const adminEditMatch = path.match(/^\/admin\/events\/([^/]+)\/edit$/)

  let page = <HomePage />
  if (eventMatch) {
    page = <EventDetailsPage slug={decodeURIComponent(eventMatch[1])} />
  } else if (path === '/events') {
    page = <ExplorePage />
  } else if (path === '/admin/login') {
    page = <AdminLogin />
  } else if (path === '/admin/dashboard') {
    page = <AdminDashboard />
  } else if (path === '/admin/events/new') {
    page = <AdminEventForm />
  } else if (adminEditMatch) {
    page = <AdminEventForm eventId={decodeURIComponent(adminEditMatch[1])} />
  }

  return (
    <>
      <header className="topbar page-shell">
        <a className="brand" href="/">
          <span className="brand-mark">T</span>
          <span>
            Tamil Event <strong>Discovery</strong>
          </span>
        </a>
        <nav>
          <a href="/events">Explore events</a>
          <a href="/admin/login">Admin</a>
          <span className="region-pill">⌖ Tamil Nadu, India</span>
        </nav>
      </header>
      {page}
      <footer className="page-shell">
        <span>Built for discovering verified opportunities across Tamil Nadu.</span>
        <span>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API docs ↗
          </a>
        </span>
      </footer>
    </>
  )
}
