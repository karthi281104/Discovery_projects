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
  const [metrics, setMetrics] = useState<DiscoveryMetrics | null>(null)
  const [sources, setSources] = useState<DiscoverySource[]>([])
  const [runs, setRuns] = useState<DiscoveryRun[]>([])
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
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

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [m, s, r, c] = await Promise.all([
        getAdminDiscoveryMetrics().catch(() => null),
        getAdminDiscoverySources().catch(() => ({ items: [], total: 0 })),
        getAdminDiscoveryRuns(1, 20).catch(() => ({ items: [], total: 0, page: 1, page_size: 20, pages: 1 })),
        getAdminDiscoveryCandidates(25).catch(() => []),
      ])
      setMetrics(m)
      setSources(s.items)
      setRuns(r.items)
      setCandidates(c)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleTriggerAll = async () => {
    setActionLoading(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const resultRuns = await triggerAdminDiscoveryAll()
      setSuccessMsg(`Discovery triggered for all enabled sources (${resultRuns.length} runs executed).`)
      await loadData()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleTriggerSource = async (sourceId: string | number) => {
    setActionLoading(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const run = await triggerAdminDiscoverySource(sourceId)
      setSuccessMsg(
        `Run completed for source #${sourceId}: ${run.events_created} created, ${run.events_updated} updated, ${run.duplicates_skipped} skipped.`
      )
      await loadData()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleToggle = async (sourceId: string | number) => {
    try {
      await toggleAdminDiscoverySource(sourceId)
      await loadData()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleDelete = async (sourceId: string | number) => {
    if (!window.confirm('Are you sure you want to delete this discovery source?')) return
    try {
      await deleteAdminDiscoverySource(sourceId)
      await loadData()
    } catch (err) {
      setError((err as Error).message)
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
    setError(null)
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
      await loadData()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="discovery-monitor">
      {/* Metrics Row */}
      <div className="metrics-grid" style={{ marginBottom: '2rem' }}>
        <div className="metric-card">
          <span>Total Sources</span>
          <strong>{metrics?.total_sources ?? sources.length}</strong>
        </div>
        <div className="metric-card">
          <span>Active Sources</span>
          <strong>{metrics?.enabled_sources ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Sources with Errors</span>
          <strong style={{ color: (metrics?.sources_with_errors ?? 0) > 0 ? '#ff6b6b' : 'inherit' }}>
            {metrics?.sources_with_errors ?? 0}
          </strong>
        </div>
        <div className="metric-card">
          <span>Events Auto-Created</span>
          <strong style={{ color: '#4caf50' }}>{metrics?.total_events_created ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Events Updated</span>
          <strong>{metrics?.total_events_updated ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Duplicates Skipped</span>
          <strong>{metrics?.total_duplicates_skipped ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Validation Failures</span>
          <strong style={{ color: (metrics?.total_validation_failures ?? 0) > 0 ? '#ffa726' : 'inherit' }}>
            {metrics?.total_validation_failures ?? 0}
          </strong>
        </div>
      </div>

      {/* Notifications */}
      {error && <div className="error-state" style={{ marginBottom: '1rem' }}>{error}</div>}
      {successMsg && <div className="success-state" style={{ padding: '0.75rem', background: 'rgba(76,175,80,0.1)', border: '1px solid #4caf50', borderRadius: '4px', marginBottom: '1rem' }}>{successMsg}</div>}

      {/* Action Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <h2>Discovery Sources ({sources.length})</h2>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={handleTriggerAll} disabled={actionLoading || loading} className="action-button">
            {actionLoading ? 'Running...' : 'Trigger All Sources'}
          </button>
          <button onClick={openAddModal} className="primary-button">
            + Add New Source
          </button>
        </div>
      </div>

      {/* Sources Table */}
      {sources.length === 0 ? (
        <div className="empty-state">No discovery sources configured. Click "+ Add New Source" to add one.</div>
      ) : (
        <div className="table-responsive" style={{ marginBottom: '3rem' }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Source Name</th>
                <th>Type</th>
                <th>Region</th>
                <th>Interval</th>
                <th>Last Run</th>
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
      )}

      {/* Recent Runs Table */}
      <h2 style={{ marginBottom: '1rem' }}>Recent Discovery Runs ({runs.length})</h2>
      {runs.length === 0 ? (
        <div className="empty-state" style={{ marginBottom: '3rem' }}>No discovery runs executed yet.</div>
      ) : (
        <div className="table-responsive" style={{ marginBottom: '3rem' }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Source</th>
                <th>Started</th>
                <th>Status</th>
                <th>Checked</th>
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
                        background: r.status === 'success' ? '#2e7d32' : r.status === 'running' ? '#f57c00' : '#c62828',
                        color: '#fff',
                        textTransform: 'uppercase',
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
      )}

      {/* Candidate Exceptions Table */}
      <h2 style={{ marginBottom: '1rem' }}>Candidate Exceptions / Validation Failures ({candidates.length})</h2>
      {candidates.length === 0 ? (
        <div className="empty-state">No candidate exceptions requiring investigation.</div>
      ) : (
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
            <p><strong>Status:</strong> {selectedRun.status}</p>
            <p><strong>Events Created:</strong> {selectedRun.events_created}</p>
            <p><strong>Events Updated:</strong> {selectedRun.events_updated}</p>
            <p><strong>Duplicates Skipped:</strong> {selectedRun.duplicates_skipped}</p>
            <p><strong>Validation Failures:</strong> {selectedRun.validation_failures}</p>
            {selectedRun.error_message && <p style={{ color: '#ff6b6b' }}><strong>Error:</strong> {selectedRun.error_message}</p>}
            <div style={{ marginTop: '1rem' }}>
              <strong>Run Metrics:</strong>
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

