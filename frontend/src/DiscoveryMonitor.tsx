import { FormEvent, useEffect, useState } from 'react'
import {
  createAdminDiscoverySource,
  deleteAdminDiscoverySource,
  getAdminDiscoveryCandidates,
  getAdminDiscoveryMetrics,
  getAdminDiscoveryRuns,
  getAdminDiscoverySources,
  getAdminPublishedEvents,
  getAdminReviewQueue,
  toggleAdminDiscoverySource,
  triggerAdminDiscoveryAll,
  triggerAdminDiscoverySource,
  triggerAdminSearchCampaign,
  updateAdminDiscoverySource,
  updateEventAction,
} from './api'
import type {
  DiscoveryCandidate,
  DiscoveryMetrics,
  DiscoveryRun,
  DiscoverySource,
  Event,
  SourceType,
} from './types'

export function DiscoveryMonitor() {
  // Navigation tab inside Discovery Monitor
  const [activeTab, setActiveTab] = useState<'sources' | 'review' | 'published' | 'exceptions'>('sources')

  // Section-level states: [data, loading, error]
  const [metrics, setMetrics] = useState<DiscoveryMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)

  const [sources, setSources] = useState<DiscoverySource[] | null>(null)
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const [sourcesError, setSourcesError] = useState<string | null>(null)

  const [runs, setRuns] = useState<DiscoveryRun[] | null>(null)
  const [runsLoading, setRunsLoading] = useState(false)
  const [runsError, setRunsError] = useState<string | null>(null)

  const [candidates, setCandidates] = useState<DiscoveryCandidate[] | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)

  // Review Queue and Published Events
  const [reviewEvents, setReviewEvents] = useState<Event[] | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)

  const [publishedEvents, setPublishedEvents] = useState<Event[] | null>(null)
  const [publishedLoading, setPublishedLoading] = useState(false)
  const [publishedError, setPublishedError] = useState<string | null>(null)

  // Evidence Drawer modal state
  const [evidenceEvent, setEvidenceEvent] = useState<Event | null>(null)

  const [actionLoading, setActionLoading] = useState(false)
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Add/Edit Source Form
  const [showSourceModal, setShowSourceModal] = useState(false)
  const [editingSourceId, setEditingSourceId] = useState<string | number | null>(null)
  const [sourceName, setSourceName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceType, setSourceType] = useState<SourceType>('rss')
  const [sourceRegion, setSourceRegion] = useState('Tamil Nadu')
  const [sourceInterval, setSourceInterval] = useState(60)

  // Run detail modal
  const [selectedRun, setSelectedRun] = useState<DiscoveryRun | null>(null)

  const loadMetrics = async () => {
    setMetricsLoading(true)
    setMetricsError(null)
    try {
      const data = await getAdminDiscoveryMetrics()
      setMetrics(data)
    } catch (err) {
      setMetricsError((err as Error).message)
    } finally {
      setMetricsLoading(false)
    }
  }

  const loadSources = async () => {
    setSourcesLoading(true)
    setSourcesError(null)
    try {
      const data = await getAdminDiscoverySources()
      setSources(data.items)
    } catch (err) {
      setSourcesError((err as Error).message)
    } finally {
      setSourcesLoading(false)
    }
  }

  const loadRuns = async () => {
    setRunsLoading(true)
    setRunsError(null)
    try {
      const data = await getAdminDiscoveryRuns(1, 20)
      setRuns(data.items)
    } catch (err) {
      setRunsError((err as Error).message)
    } finally {
      setRunsLoading(false)
    }
  }

  const loadCandidates = async () => {
    setCandidatesLoading(true)
    setCandidatesError(null)
    try {
      const data = await getAdminDiscoveryCandidates(25)
      setCandidates(data)
    } catch (err) {
      setCandidatesError((err as Error).message)
    } finally {
      setCandidatesLoading(false)
    }
  }

  const loadReviewQueue = async () => {
    setReviewLoading(true)
    setReviewError(null)
    try {
      const data = await getAdminReviewQueue(50)
      setReviewEvents(data)
    } catch (err) {
      setReviewError((err as Error).message)
    } finally {
      setReviewLoading(false)
    }
  }

  const loadPublishedEvents = async () => {
    setPublishedLoading(true)
    setPublishedError(null)
    try {
      const data = await getAdminPublishedEvents(50)
      setPublishedEvents(data)
    } catch (err) {
      setPublishedError((err as Error).message)
    } finally {
      setPublishedLoading(false)
    }
  }

  const loadAll = () => {
    loadMetrics()
    loadSources()
    loadRuns()
    loadCandidates()
    loadReviewQueue()
    loadPublishedEvents()
  }

  useEffect(() => {
    loadAll()
  }, [])

  const handleTriggerAll = async () => {
    setActionLoading(true)
    setGlobalError(null)
    setSuccessMsg(null)
    try {
      const resultRuns = await triggerAdminDiscoveryAll()
      setSuccessMsg(`Discovery triggered for all enabled sources (${resultRuns.length} runs executed).`)
      loadAll()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleSearchCampaign = async () => {
    setActionLoading(true)
    setGlobalError(null)
    setSuccessMsg(null)
    try {
      const campaign = await triggerAdminSearchCampaign()
      setSuccessMsg(
        `Search campaign completed: ${campaign.results_collected} results and ${campaign.sources_discovered} new sources.`
      )
      loadAll()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleTriggerSource = async (sourceId: string | number) => {
    setActionLoading(true)
    setGlobalError(null)
    setSuccessMsg(null)
    try {
      const run = await triggerAdminDiscoverySource(sourceId)
      setSuccessMsg(
        `Run #${run.id} finished (${run.status}): ${run.events_created} created, ${run.events_updated} updated, ${run.duplicates_skipped} skipped, ${run.validation_failures} failed.`
      )
      loadAll()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleToggle = async (sourceId: string | number) => {
    try {
      await toggleAdminDiscoverySource(sourceId)
      loadSources()
      loadMetrics()
    } catch (err) {
      setGlobalError((err as Error).message)
    }
  }

  const handleDelete = async (sourceId: string | number) => {
    if (!window.confirm('Are you sure you want to delete this discovery source?')) return
    try {
      await deleteAdminDiscoverySource(sourceId)
      loadSources()
      loadMetrics()
    } catch (err) {
      setGlobalError((err as Error).message)
    }
  }

  const handleApprove = async (eventId: string | number) => {
    setActionLoading(true)
    try {
      await updateEventAction(eventId, 'publish')
      setSuccessMsg(`Event #${eventId} successfully approved and published!`)
      if (evidenceEvent && evidenceEvent.id === eventId) {
        setEvidenceEvent(null)
      }
      loadReviewQueue()
      loadPublishedEvents()
      loadMetrics()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (eventId: string | number) => {
    if (!window.confirm('Are you sure you want to reject this event candidate?')) return
    setActionLoading(true)
    try {
      await updateEventAction(eventId, 'reject')
      setSuccessMsg(`Event #${eventId} rejected.`)
      if (evidenceEvent && evidenceEvent.id === eventId) {
        setEvidenceEvent(null)
      }
      loadReviewQueue()
      loadMetrics()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const openAddModal = () => {
    setEditingSourceId(null)
    setSourceName('')
    setSourceUrl('')
    setSourceType('rss')
    setSourceRegion('Tamil Nadu')
    setSourceInterval(60)
    setShowSourceModal(true)
  }

  const openEditModal = (src: DiscoverySource) => {
    setEditingSourceId(src.id)
    setSourceName(src.name)
    setSourceUrl(src.base_url)
    setSourceType(src.source_type)
    setSourceRegion(src.region)
    setSourceInterval(src.crawl_interval)
    setShowSourceModal(true)
  }

  const handleSaveSource = async (e: FormEvent) => {
    e.preventDefault()
    setActionLoading(true)
    setGlobalError(null)
    try {
      if (editingSourceId) {
        await updateAdminDiscoverySource(editingSourceId, {
          name: sourceName,
          base_url: sourceUrl,
          source_type: sourceType,
          region: sourceRegion,
          crawl_interval: Number(sourceInterval),
        })
        setSuccessMsg('Discovery source updated successfully.')
      } else {
        await createAdminDiscoverySource({
          name: sourceName,
          base_url: sourceUrl,
          source_type: sourceType,
          region: sourceRegion,
          crawl_interval: Number(sourceInterval),
          is_enabled: true,
        })
        setSuccessMsg('New discovery source added successfully.')
      }
      setShowSourceModal(false)
      loadSources()
      loadMetrics()
    } catch (err) {
      setGlobalError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case 'success':
      case 'published':
      case 'auto_published':
        return { background: '#2e7d32', color: '#fff' }
      case 'partial':
      case 'needs_review':
      case 'pending':
        return { background: '#ef6c00', color: '#fff' }
      case 'running':
        return { background: '#1976d2', color: '#fff' }
      default:
        return { background: '#c62828', color: '#fff' }
    }
  }

  return (
    <div className="discovery-monitor">
      {/* Global Notifications */}
      {globalError && <div className="error-state" style={{ marginBottom: '1rem' }}>{globalError}</div>}
      {successMsg && (
        <div className="success-state" style={{ padding: '0.75rem', background: 'rgba(76,175,80,0.1)', border: '1px solid #4caf50', borderRadius: '4px', marginBottom: '1rem' }}>
          {successMsg}
        </div>
      )}

      {/* Full 14 Telemetry Metrics Grid */}
      {metricsError ? (
        <div className="error-state" style={{ marginBottom: '1.5rem' }}>
          <span>Failed to load discovery metrics: {metricsError}</span>
          <button onClick={loadMetrics} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
        </div>
      ) : metricsLoading && !metrics ? (
        <div className="loading-state" style={{ marginBottom: '1.5rem' }}>Loading discovery telemetry metrics...</div>
      ) : (
        <div className="metrics-grid" style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem' }}>
          {/* 1. queries_executed */}
          <div className="metric-card">
            <span>Queries Executed</span>
            <strong>{metrics !== null ? metrics.queries_executed : '—'}</strong>
          </div>
          {/* 2. search_results_collected */}
          <div className="metric-card">
            <span>Search Results</span>
            <strong>{metrics !== null ? metrics.search_results_collected : '—'}</strong>
          </div>
          {/* 3. new_urls_discovered */}
          <div className="metric-card">
            <span>URLs Discovered</span>
            <strong style={{ color: '#64b5f6' }}>{metrics !== null ? metrics.new_urls_discovered : '—'}</strong>
          </div>
          {/* 4. new_sources_identified */}
          <div className="metric-card">
            <span>Sources Identified</span>
            <strong>{metrics !== null ? metrics.new_sources_identified : '—'}</strong>
          </div>
          {/* 5. pages_successfully_fetched */}
          <div className="metric-card">
            <span>Pages Fetched</span>
            <strong>{metrics !== null ? metrics.pages_successfully_fetched : '—'}</strong>
          </div>
          {/* 6. pages_blocked_or_inaccessible */}
          <div className="metric-card">
            <span>Blocked / Inaccessible</span>
            <strong style={{ color: (metrics?.pages_blocked_or_inaccessible ?? 0) > 0 ? '#ffb74d' : 'inherit' }}>
              {metrics !== null ? metrics.pages_blocked_or_inaccessible : '—'}
            </strong>
          </div>
          {/* 7. event_candidates_extracted */}
          <div className="metric-card">
            <span>Candidates Extracted</span>
            <strong>{metrics !== null ? metrics.event_candidates_extracted : '—'}</strong>
          </div>
          {/* 8. valid_events */}
          <div className="metric-card">
            <span>Valid Events</span>
            <strong style={{ color: '#81c784' }}>{metrics !== null ? metrics.valid_events : '—'}</strong>
          </div>
          {/* 9. events_published */}
          <div className="metric-card">
            <span>Events Published</span>
            <strong style={{ color: '#4caf50' }}>{metrics !== null ? metrics.events_published : '—'}</strong>
          </div>
          {/* 10. candidates_requiring_review */}
          <div className="metric-card">
            <span>Needs Review</span>
            <strong style={{ color: (metrics?.candidates_requiring_review ?? 0) > 0 ? '#ff9800' : 'inherit' }}>
              {metrics !== null ? metrics.candidates_requiring_review : '—'}
            </strong>
          </div>
          {/* 11. duplicates_detected */}
          <div className="metric-card">
            <span>Duplicates Detected</span>
            <strong>{metrics !== null ? metrics.duplicates_detected : '—'}</strong>
          </div>
          {/* 12. events_updated */}
          <div className="metric-card">
            <span>Events Updated</span>
            <strong style={{ color: '#4fc3f7' }}>{metrics !== null ? metrics.events_updated : '—'}</strong>
          </div>
          {/* 13. source_failures */}
          <div className="metric-card">
            <span>Source Failures</span>
            <strong style={{ color: (metrics?.source_failures ?? 0) > 0 ? '#ff6b6b' : 'inherit' }}>
              {metrics !== null ? metrics.source_failures : '—'}
            </strong>
          </div>
          {/* 14. discovery_execution_duration */}
          <div className="metric-card">
            <span>Execution Duration</span>
            <strong>{metrics !== null ? `${metrics.discovery_execution_duration}s` : '—'}</strong>
          </div>
        </div>
      )}

      {/* Discovery Sub-Navigation */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid #333', paddingBottom: '0.75rem', flexWrap: 'wrap' }}>
        <button
          onClick={() => setActiveTab('sources')}
          style={{
            padding: '0.5rem 1rem',
            background: activeTab === 'sources' ? '#333' : 'transparent',
            border: activeTab === 'sources' ? '1px solid #555' : '1px solid transparent',
            color: activeTab === 'sources' ? '#fff' : '#aaa',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: activeTab === 'sources' ? 'bold' : 'normal',
          }}
        >
          🌐 Discovery Sources & Runs {sources ? `(${sources.length})` : ''}
        </button>
        <button
          onClick={() => {
            setActiveTab('review')
            loadReviewQueue()
          }}
          style={{
            padding: '0.5rem 1rem',
            background: activeTab === 'review' ? '#333' : 'transparent',
            border: activeTab === 'review' ? '1px solid #ff9800' : '1px solid transparent',
            color: activeTab === 'review' ? '#ff9800' : '#aaa',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: activeTab === 'review' ? 'bold' : 'normal',
          }}
        >
          📝 Review Queue {reviewEvents ? `(${reviewEvents.length})` : ''}
        </button>
        <button
          onClick={() => {
            setActiveTab('published')
            loadPublishedEvents()
          }}
          style={{
            padding: '0.5rem 1rem',
            background: activeTab === 'published' ? '#333' : 'transparent',
            border: activeTab === 'published' ? '1px solid #4caf50' : '1px solid transparent',
            color: activeTab === 'published' ? '#4caf50' : '#aaa',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: activeTab === 'published' ? 'bold' : 'normal',
          }}
        >
          ✅ Published Events {publishedEvents ? `(${publishedEvents.length})` : ''}
        </button>
        <button
          onClick={() => setActiveTab('exceptions')}
          style={{
            padding: '0.5rem 1rem',
            background: activeTab === 'exceptions' ? '#333' : 'transparent',
            border: activeTab === 'exceptions' ? '1px solid #555' : '1px solid transparent',
            color: activeTab === 'exceptions' ? '#fff' : '#aaa',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: activeTab === 'exceptions' ? 'bold' : 'normal',
          }}
        >
          ⚠️ Exceptions {candidates ? `(${candidates.length})` : ''}
        </button>
      </div>

      {/* Tab 1: Sources & Runs */}
      {activeTab === 'sources' && (
        <>
          {/* Sources Section Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
            <h2>Discovery Sources {sources !== null ? `(${sources.length})` : ''}</h2>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button onClick={handleTriggerAll} disabled={actionLoading || sourcesLoading} className="action-button">
                {actionLoading ? 'Running...' : 'Trigger All Sources'}
              </button>
              <button onClick={handleSearchCampaign} disabled={actionLoading} className="action-button">
                Search Internet
              </button>
              <button onClick={openAddModal} className="primary-button">
                + Add New Source
              </button>
            </div>
          </div>

          {/* Sources Table */}
          {sourcesError ? (
            <div className="error-state" style={{ marginBottom: '3rem' }}>
              <span>Failed to load discovery sources: {sourcesError}</span>
              <button onClick={loadSources} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : sourcesLoading && sources === null ? (
            <div className="loading-state" style={{ marginBottom: '3rem' }}>Loading discovery sources...</div>
          ) : sources !== null && sources.length === 0 ? (
            <div className="empty-state" style={{ marginBottom: '3rem' }}>No discovery sources configured. Click "+ Add New Source" to add one.</div>
          ) : sources !== null ? (
            <div className="table-responsive" style={{ marginBottom: '3rem' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Source Name</th>
                    <th>Type</th>
                    <th>Region</th>
                    <th>Interval</th>
                    <th>Last Checked</th>
                    <th>Last Success</th>
                    <th>Last Error</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((src) => (
                    <tr key={src.id}>
                      <td>
                        <button
                          onClick={() => handleToggle(src.id)}
                          style={{
                            padding: '0.25rem 0.5rem',
                            fontSize: '0.75rem',
                            borderRadius: '4px',
                            background: src.is_enabled ? '#2e7d32' : '#555',
                            color: '#fff',
                            border: 'none',
                            cursor: 'pointer',
                          }}
                          title={src.is_enabled ? 'Click to Disable' : 'Click to Enable'}
                        >
                          {src.is_enabled ? 'ENABLED' : 'DISABLED'}
                        </button>
                      </td>
                      <td>
                        <strong>{src.name}</strong>
                        <br />
                        <small style={{ color: '#888', wordBreak: 'break-all' }}>{src.base_url}</small>
                      </td>
                      <td>
                        <span style={{ textTransform: 'uppercase', fontSize: '0.75rem', padding: '0.2rem 0.4rem', background: '#333', borderRadius: '4px' }}>
                          {src.source_type}
                        </span>
                      </td>
                      <td>{src.region}</td>
                      <td>{src.crawl_interval}m</td>
                      <td>
                        {src.last_crawl_time ? new Date(src.last_crawl_time).toLocaleString() : 'Never'}
                      </td>
                      <td>
                        {src.last_success_time ? new Date(src.last_success_time).toLocaleString() : 'Never'}
                      </td>
                      <td style={{ maxWidth: '200px', wordBreak: 'break-word', color: src.last_error ? '#ff6b6b' : '#888' }}>
                        {src.last_error ? src.last_error.substring(0, 80) : 'None'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            onClick={() => handleTriggerSource(src.id)}
                            disabled={actionLoading}
                            style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}
                          >
                            Run Now
                          </button>
                          <button
                            onClick={() => openEditModal(src)}
                            style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(src.id)}
                            style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: '#ff6b6b' }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {/* Recent Runs Section */}
          <h2 style={{ marginBottom: '1rem' }}>Recent Discovery Runs {runs !== null ? `(${runs.length})` : ''}</h2>
          {runsError ? (
            <div className="error-state" style={{ marginBottom: '3rem' }}>
              <span>Failed to load recent discovery runs: {runsError}</span>
              <button onClick={loadRuns} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : runsLoading && runs === null ? (
            <div className="loading-state" style={{ marginBottom: '3rem' }}>Loading discovery runs...</div>
          ) : runs !== null && runs.length === 0 ? (
            <div className="empty-state" style={{ marginBottom: '3rem' }}>No discovery runs executed yet.</div>
          ) : runs !== null ? (
            <div className="table-responsive" style={{ marginBottom: '3rem' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Source</th>
                    <th>Started</th>
                    <th>Status</th>
                    <th>Pages Checked</th>
                    <th>Created</th>
                    <th>Updated</th>
                    <th>Skipped</th>
                    <th>Failures</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td>#{r.id}</td>
                      <td>{r.source_name || `Source #${r.source_id}`}</td>
                      <td>{new Date(r.started_at).toLocaleString()}</td>
                      <td>
                        <span
                          style={{
                            padding: '0.2rem 0.4rem',
                            fontSize: '0.75rem',
                            borderRadius: '4px',
                            textTransform: 'uppercase',
                            fontWeight: 'bold',
                            ...getStatusBadgeStyle(r.status),
                          }}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td>{r.pages_checked}</td>
                      <td style={{ color: r.events_created > 0 ? '#4caf50' : 'inherit', fontWeight: r.events_created > 0 ? 'bold' : 'normal' }}>
                        {r.events_created}
                      </td>
                      <td>{r.events_updated}</td>
                      <td>{r.duplicates_skipped}</td>
                      <td style={{ color: r.validation_failures > 0 ? '#ffa726' : 'inherit' }}>{r.validation_failures}</td>
                      <td>
                        <button
                          onClick={() => setSelectedRun(r)}
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', cursor: 'pointer' }}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}

      {/* Tab 2: Review Queue */}
      {activeTab === 'review' && (
        <div style={{ marginBottom: '3rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2>Review Queue (Candidates Requiring Review)</h2>
            <button onClick={loadReviewQueue} disabled={reviewLoading} style={{ padding: '0.4rem 0.8rem', cursor: 'pointer' }}>
              {reviewLoading ? 'Refreshing...' : 'Refresh Queue'}
            </button>
          </div>

          {reviewError ? (
            <div className="error-state">
              <span>Failed to load review queue: {reviewError}</span>
              <button onClick={loadReviewQueue} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : reviewLoading && reviewEvents === null ? (
            <div className="loading-state">Loading candidate events awaiting review...</div>
          ) : reviewEvents !== null && reviewEvents.length === 0 ? (
            <div className="empty-state">🎉 Great! No event candidates are currently awaiting manual review.</div>
          ) : reviewEvents !== null ? (
            <div className="table-responsive">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Confidence</th>
                    <th>Event Details</th>
                    <th>Location</th>
                    <th>Start Date</th>
                    <th>Source Evidence</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewEvents.map((ev) => (
                    <tr key={ev.id}>
                      <td>
                        <span
                          style={{
                            padding: '0.25rem 0.5rem',
                            fontSize: '0.75rem',
                            borderRadius: '4px',
                            fontWeight: 'bold',
                            background: '#ef6c00',
                            color: '#fff',
                            display: 'inline-block',
                          }}
                        >
                          {typeof ev.confidence_score === 'number' ? `${(ev.confidence_score * 100).toFixed(0)}%` : 'Review'}
                        </span>
                        <div style={{ fontSize: '0.7rem', color: '#aaa', marginTop: '0.2rem' }}>
                          {ev.validation_outcome || 'needs_review'}
                        </div>
                      </td>
                      <td>
                        <strong>{ev.title}</strong>
                        {ev.organizer_name && (
                          <div style={{ fontSize: '0.8rem', color: '#888' }}>Org: {ev.organizer_name}</div>
                        )}
                      </td>
                      <td>{ev.city ? `${ev.city}, TN` : (ev.venue || 'Tamil Nadu')}</td>
                      <td>{ev.start_date ? new Date(ev.start_date).toLocaleDateString() : 'N/A'}</td>
                      <td>
                        <button
                          onClick={() => setEvidenceEvent(ev)}
                          style={{
                            padding: '0.25rem 0.6rem',
                            fontSize: '0.75rem',
                            background: '#1976d2',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          🔍 Evidence Drawer
                        </button>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <button
                            onClick={() => handleApprove(ev.id)}
                            disabled={actionLoading}
                            style={{
                              padding: '0.25rem 0.6rem',
                              fontSize: '0.75rem',
                              background: '#2e7d32',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                            }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(ev.id)}
                            disabled={actionLoading}
                            style={{
                              padding: '0.25rem 0.6rem',
                              fontSize: '0.75rem',
                              background: '#c62828',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}

      {/* Tab 3: Published Events */}
      {activeTab === 'published' && (
        <div style={{ marginBottom: '3rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2>Published Events (Discovered & Auto-Published)</h2>
            <button onClick={loadPublishedEvents} disabled={publishedLoading} style={{ padding: '0.4rem 0.8rem', cursor: 'pointer' }}>
              {publishedLoading ? 'Refreshing...' : 'Refresh List'}
            </button>
          </div>

          {publishedError ? (
            <div className="error-state">
              <span>Failed to load published events: {publishedError}</span>
              <button onClick={loadPublishedEvents} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : publishedLoading && publishedEvents === null ? (
            <div className="loading-state">Loading published events...</div>
          ) : publishedEvents !== null && publishedEvents.length === 0 ? (
            <div className="empty-state">No published events found.</div>
          ) : publishedEvents !== null ? (
            <div className="table-responsive">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Event Details</th>
                    <th>City / Venue</th>
                    <th>Start Date</th>
                    <th>Confidence</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {publishedEvents.map((ev) => (
                    <tr key={ev.id}>
                      <td>
                        <span
                          style={{
                            padding: '0.2rem 0.4rem',
                            fontSize: '0.75rem',
                            borderRadius: '4px',
                            background: '#2e7d32',
                            color: '#fff',
                            fontWeight: 'bold',
                          }}
                        >
                          PUBLISHED
                        </span>
                      </td>
                      <td>
                        <strong>{ev.title}</strong>
                        {ev.organizer_name && <small style={{ display: 'block', color: '#888' }}>By {ev.organizer_name}</small>}
                      </td>
                      <td>{ev.city ? `${ev.city}, TN` : (ev.venue || 'Tamil Nadu')}</td>
                      <td>{ev.start_date ? new Date(ev.start_date).toLocaleDateString() : 'N/A'}</td>
                      <td>
                        <span style={{ color: '#81c784', fontWeight: 'bold' }}>
                          {typeof ev.confidence_score === 'number' ? `${(ev.confidence_score * 100).toFixed(0)}%` : 'High'}
                        </span>
                      </td>
                      <td>
                        <button
                          onClick={() => setEvidenceEvent(ev)}
                          style={{
                            padding: '0.25rem 0.6rem',
                            fontSize: '0.75rem',
                            background: '#333',
                            color: '#fff',
                            border: '1px solid #555',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          🔍 View Evidence
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}

      {/* Tab 4: Candidate Exceptions */}
      {activeTab === 'exceptions' && (
        <div>
          <h2 style={{ marginBottom: '1rem' }}>Candidate Exceptions / Validation Failures {candidates !== null ? `(${candidates.length})` : ''}</h2>
          {candidatesError ? (
            <div className="error-state">
              <span>Failed to load candidate exceptions: {candidatesError}</span>
              <button onClick={loadCandidates} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : candidatesLoading && candidates === null ? (
            <div className="loading-state">Loading candidate exceptions...</div>
          ) : candidates !== null && candidates.length === 0 ? (
            <div className="empty-state">No candidate exceptions requiring investigation.</div>
          ) : candidates !== null ? (
            <div className="table-responsive">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Candidate Title</th>
                    <th>Source URL</th>
                    <th>Rejection Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((cand, idx) => (
                    <tr key={idx}>
                      <td>
                        <strong>{cand.title}</strong>
                        {cand.source_name && <small style={{ display: 'block', color: '#888' }}>via {cand.source_name}</small>}
                      </td>
                      <td>
                        <a href={cand.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#64b5f6', fontSize: '0.85rem' }}>
                          {cand.source_url.length > 50 ? `${cand.source_url.substring(0, 50)}...` : cand.source_url}
                        </a>
                      </td>
                      <td>
                        <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#ffa726', fontSize: '0.85rem' }}>
                          {cand.rejection_reasons.map((reason, rIdx) => (
                            <li key={rIdx}>{reason}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}

      {/* Source Modal */}
      {showSourceModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="modal-card" style={{ background: '#1e1e1e', padding: '2rem', borderRadius: '8px', width: '100%', maxWidth: '500px', border: '1px solid #333' }}>
            <h3>{editingSourceId ? 'Edit Discovery Source' : 'Add New Discovery Source'}</h3>
            <form onSubmit={handleSaveSource} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
              <label>
                Source Name
                <input required value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="e.g. Chennai Tech Events RSS" />
              </label>
              <label>
                Base / Feed URL
                <input required type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://example.com/feed.xml" />
              </label>
              <label>
                Source Type
                <select value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)}>
                  <option value="rss">RSS / Atom XML Feed</option>
                  <option value="jsonld">Schema.org JSON-LD Event Webpage</option>
                  <option value="html">HTML Semantic Listing</option>
                  <option value="api">REST JSON API</option>
                </select>
              </label>
              <label>
                Region / Coverage
                <input value={sourceRegion} onChange={(e) => setSourceRegion(e.target.value)} placeholder="e.g. Tamil Nadu, Chennai, Coimbatore" />
              </label>
              <label>
                Crawl Interval (Minutes)
                <input type="number" min="1" value={sourceInterval} onChange={(e) => setSourceInterval(Number(e.target.value))} />
              </label>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" onClick={() => setShowSourceModal(false)} style={{ background: 'none', border: '1px solid #555', color: '#fff', padding: '0.5rem 1rem', cursor: 'pointer' }}>
                  Cancel
                </button>
                <button type="submit" disabled={actionLoading} style={{ background: '#4caf50', border: 'none', color: '#fff', padding: '0.5rem 1rem', cursor: 'pointer' }}>
                  {actionLoading ? 'Saving...' : 'Save Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Run Detail Modal */}
      {selectedRun && (
        <div className="modal-backdrop" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="modal-card" style={{ background: '#1e1e1e', padding: '2rem', borderRadius: '8px', width: '100%', maxWidth: '600px', border: '1px solid #333' }}>
            <h3>Discovery Run Details #{selectedRun.id}</h3>
            <p><strong>Source:</strong> {selectedRun.source_name || `Source #${selectedRun.source_id}`}</p>
            <p><strong>Started:</strong> {new Date(selectedRun.started_at).toLocaleString()}</p>
            <p>
              <strong>Status:</strong>{' '}
              <span style={{ padding: '0.2rem 0.4rem', borderRadius: '4px', textTransform: 'uppercase', ...getStatusBadgeStyle(selectedRun.status) }}>
                {selectedRun.status}
              </span>
            </p>
            <p><strong>Pages Checked:</strong> {selectedRun.pages_checked}</p>
            <p><strong>Candidates Found:</strong> {selectedRun.candidates_found}</p>
            <p><strong>Events Created:</strong> {selectedRun.events_created}</p>
            <p><strong>Events Updated:</strong> {selectedRun.events_updated}</p>
            <p><strong>Duplicates Skipped:</strong> {selectedRun.duplicates_skipped}</p>
            <p><strong>Validation Failures:</strong> {selectedRun.validation_failures}</p>
            {selectedRun.error_message && <p style={{ color: '#ff6b6b' }}><strong>Error:</strong> {selectedRun.error_message}</p>}
            <div style={{ marginTop: '1rem' }}>
              <strong>Run Metrics & Exceptions:</strong>
              <pre style={{ background: '#111', padding: '1rem', borderRadius: '4px', overflow: 'auto', maxHeight: '200px' }}>
                {JSON.stringify(selectedRun.metrics, null, 2)}
              </pre>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button onClick={() => setSelectedRun(null)} style={{ background: '#4caf50', border: 'none', color: '#fff', padding: '0.5rem 1rem', cursor: 'pointer' }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EVIDENCE DRAWER MODAL */}
      {evidenceEvent && (
        <div
          className="modal-backdrop"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
          }}
        >
          <div
            className="evidence-drawer"
            style={{
              background: '#1e1e1e',
              border: '1px solid #444',
              borderRadius: '8px',
              padding: '2rem',
              width: '100%',
              maxWidth: '750px',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #333', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <span
                  style={{
                    fontSize: '0.75rem',
                    textTransform: 'uppercase',
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                    fontWeight: 'bold',
                    ...getStatusBadgeStyle(evidenceEvent.validation_outcome || evidenceEvent.status),
                  }}
                >
                  {evidenceEvent.validation_outcome || evidenceEvent.status}
                </span>
                <h3 style={{ margin: '0.5rem 0 0 0', color: '#fff' }}>Evidence Drawer: {evidenceEvent.title}</h3>
                <small style={{ color: '#888' }}>Event ID: #{evidenceEvent.id}</small>
              </div>
              <button
                onClick={() => setEvidenceEvent(null)}
                style={{ background: 'none', border: 'none', color: '#aaa', fontSize: '1.5rem', cursor: 'pointer' }}
              >
                &times;
              </button>
            </div>

            {/* 1. Original Source URL */}
            <div style={{ marginBottom: '1.25rem', background: '#141414', padding: '1rem', borderRadius: '6px' }}>
              <strong style={{ display: 'block', color: '#64b5f6', marginBottom: '0.4rem' }}>
                🔗 Original Source URL
              </strong>
              {evidenceEvent.original_source_url ? (
                <a
                  href={evidenceEvent.original_source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#90caf9', wordBreak: 'break-all', textDecoration: 'underline' }}
                >
                  {evidenceEvent.original_source_url}
                </a>
              ) : (
                <span style={{ color: '#888' }}>
                  {evidenceEvent.official_website ? (
                    <a href={evidenceEvent.official_website} target="_blank" rel="noopener noreferrer" style={{ color: '#90caf9' }}>
                      {evidenceEvent.official_website}
                    </a>
                  ) : 'Not specified'}
                </span>
              )}
            </div>

            {/* 2. Clickable Additional Source URLs */}
            <div style={{ marginBottom: '1.25rem', background: '#141414', padding: '1rem', borderRadius: '6px' }}>
              <strong style={{ display: 'block', color: '#81c784', marginBottom: '0.4rem' }}>
                🌐 Additional Source URLs ({evidenceEvent.additional_source_urls?.length ?? 0})
              </strong>
              {evidenceEvent.additional_source_urls && evidenceEvent.additional_source_urls.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {evidenceEvent.additional_source_urls.map((url, uIdx) => (
                    <li key={uIdx}>
                      <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: '#a5d6a7', wordBreak: 'break-all' }}>
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: '#888', fontSize: '0.85rem' }}>No cross-source duplicate URLs recorded yet.</span>
              )}
            </div>

            {/* 3. Timestamps */}
            <div style={{ marginBottom: '1.25rem', background: '#141414', padding: '1rem', borderRadius: '6px' }}>
              <strong style={{ display: 'block', color: '#ffb74d', marginBottom: '0.6rem' }}>
                ⏱️ Discovery & Ingestion Timestamps
              </strong>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ color: '#888', display: 'block' }}>Discovered At:</span>
                  <strong>{evidenceEvent.discovered_at ? new Date(evidenceEvent.discovered_at).toLocaleString() : (evidenceEvent.created_at ? new Date(evidenceEvent.created_at).toLocaleString() : 'N/A')}</strong>
                </div>
                <div>
                  <span style={{ color: '#888', display: 'block' }}>Extracted At:</span>
                  <strong>{evidenceEvent.extracted_at ? new Date(evidenceEvent.extracted_at).toLocaleString() : 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: '#888', display: 'block' }}>Verified At:</span>
                  <strong>{evidenceEvent.verified_at ? new Date(evidenceEvent.verified_at).toLocaleString() : 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ color: '#888', display: 'block' }}>Last Updated:</span>
                  <strong>{evidenceEvent.updated_at ? new Date(evidenceEvent.updated_at).toLocaleString() : 'N/A'}</strong>
                </div>
              </div>
            </div>

            {/* 4. Collapsible update_history Diffs */}
            <div style={{ marginBottom: '1.5rem', background: '#141414', padding: '1rem', borderRadius: '6px' }}>
              <details open={Boolean(evidenceEvent.update_history && evidenceEvent.update_history.length > 0)}>
                <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#ba68c8' }}>
                  📜 Update History Diffs ({evidenceEvent.update_history?.length ?? 0})
                </summary>
                <div style={{ marginTop: '0.75rem' }}>
                  {evidenceEvent.update_history && evidenceEvent.update_history.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {evidenceEvent.update_history.map((diff, dIdx) => (
                        <div
                          key={dIdx}
                          style={{
                            background: '#1b1b1b',
                            border: '1px solid #333',
                            borderRadius: '4px',
                            padding: '0.75rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#888', marginBottom: '0.5rem' }}>
                            <span>Timestamp: {new Date(diff.timestamp).toLocaleString()}</span>
                            {diff.source_url && (
                              <span style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                Source: {diff.source_url}
                              </span>
                            )}
                          </div>
                          <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ color: '#aaa', borderBottom: '1px solid #333' }}>
                                <th style={{ textAlign: 'left', padding: '0.2rem' }}>Field</th>
                                <th style={{ textAlign: 'left', padding: '0.2rem', color: '#ef5350' }}>Previous Value</th>
                                <th style={{ textAlign: 'left', padding: '0.2rem', color: '#66bb6a' }}>Updated Value</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(diff.changes || {}).map(([field, vals]) => (
                                <tr key={field} style={{ borderBottom: '1px solid #222' }}>
                                  <td style={{ padding: '0.25rem', fontWeight: 'bold' }}>{field}</td>
                                  <td style={{ padding: '0.25rem', color: '#ef5350' }}>{String(vals.old ?? 'None')}</td>
                                  <td style={{ padding: '0.25rem', color: '#66bb6a' }}>{String(vals.new ?? 'None')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: '#888', fontSize: '0.85rem' }}>
                      No field diffs recorded yet. Content is at its original extracted state.
                    </div>
                  )}
                </div>
              </details>
            </div>

            {/* Drawer Footer Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', borderTop: '1px solid #333', paddingTop: '1rem' }}>
              {evidenceEvent.validation_outcome === 'needs_review' || evidenceEvent.status === 'pending' ? (
                <>
                  <button
                    onClick={() => handleApprove(evidenceEvent.id)}
                    disabled={actionLoading}
                    style={{ background: '#2e7d32', border: 'none', color: '#fff', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
                  >
                    Approve & Publish
                  </button>
                  <button
                    onClick={() => handleReject(evidenceEvent.id)}
                    disabled={actionLoading}
                    style={{ background: '#c62828', border: 'none', color: '#fff', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
                  >
                    Reject
                  </button>
                </>
              ) : null}
              <button
                onClick={() => setEvidenceEvent(null)}
                style={{ background: '#333', border: '1px solid #555', color: '#fff', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
