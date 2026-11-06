import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { HomePage, ExplorePage, EventDetailsPage, NotFoundPage } from './pages'
import { AdminDashboard, AdminEventForm, AdminLogin } from './admin'

export function AppRoutes() {
  return (
    <>
      <header className="topbar page-shell">
        <Link className="brand" to="/">
          <span className="brand-mark">T</span>
          <span>
            Tamil Event <strong>Discovery</strong>
          </span>
        </Link>
        <nav>
          <Link to="/events">Explore events</Link>
          <Link to="/admin/login">Admin</Link>
          <span className="region-pill">⌖ Tamil Nadu, India</span>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/events" element={<ExplorePage />} />
        <Route path="/events/:slug" element={<EventDetailsPage />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin/events/new" element={<AdminEventForm />} />
        <Route path="/admin/events/:id/edit" element={<AdminEventForm />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>

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

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
