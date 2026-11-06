import { FormEvent, useEffect, useState } from 'react'
import {
  createAdminDiscoverySource,
  deleteAdminDiscoverySource,
  getAdminDiscoveryCandidates,
  getAdminDiscoveryMetrics,
  getAdminDiscoveryRuns,
  getAdminDiscoverySources,
  toggleAdminDiscoverySource,
  triggerAdminDiscoveryAll,
  triggerAdminDiscoverySource,
  triggerAdminSearchCampaign,
  updateAdminDiscoverySource,
} from './api'
import type {
  DiscoveryCandidate,
  DiscoveryMetrics,
  DiscoveryRun,
  DiscoverySource,
  SourceType,
} from './types'

export function DiscoveryMonitor() {
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

  const loadAll = () => {
    loadMetrics()
    loadSources()
    loadRuns()
    loadCandidates()
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
        return { background: '#2e7d32', color: '#fff' }
      case 'partial':
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

      {/* Metrics Section */}
      {metricsError ? (
        <div className="error-state" style={{ marginBottom: '2rem' }}>
          <span>Failed to load discovery metrics: {metricsError}</span>
          <button onClick={loadMetrics} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
        </div>
      ) : metricsLoading && !metrics ? (
        <div className="loading-state" style={{ marginBottom: '2rem' }}>Loading discovery metrics...</div>
      ) : (
        <div className="metrics-grid" style={{ marginBottom: '2rem' }}>
          <div className="metric-card">
            <span>Total Sources</span>
            <strong>{metrics !== null ? metrics.total_sources : '—'}</strong>
          </div>
          <div className="metric-card">
            <span>Active Sources</span>
            <strong>{metrics !== null ? metrics.enabled_sources : '—'}</strong>
          </div>
          <div className="metric-card">
            <span>Sources with Errors</span>
            <strong style={{ color: (metrics?.sources_with_errors ?? 0) > 0 ? '#ff6b6b' : 'inherit' }}>
              {metrics !== null ? metrics.sources_with_errors : '—'}
            </strong>
          </div>
          <div className="metric-card">
            <span>Events Auto-Created</span>
            <strong style={{ color: '#4caf50' }}>{metrics !== null ? metrics.total_events_created : '—'}</strong>
          </div>
          <div className="metric-card">
            <span>Events Updated</span>
            <strong>{metrics !== null ? metrics.total_events_updated : '—'}</strong>
          </div>
          <div className="metric-card">
            <span>Duplicates Skipped</span>
            <strong>{metrics !== null ? metrics.total_duplicates_skipped : '—'}</strong>
          </div>
          <div className="metric-card">
            <span>Validation Failures</span>
            <strong style={{ color: (metrics?.total_validation_failures ?? 0) > 0 ? '#ffa726' : 'inherit' }}>
              {metrics !== null ? metrics.total_validation_failures : '—'}
            </strong>
          </div>
        </div>
      )}

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

      {/* Sources Section Body */}
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

      {/* Candidate Exceptions Section */}
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
    </div>
  )
}
