import { useEffect, useState, Fragment } from 'react'
import { api } from '../api/client'
import type { Job } from '../api/types'

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    async function fetchJobs() {
      try {
        const data = await api.getJobs(50)
        setJobs(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchJobs()
  }, [])

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>

  // Compute stats
  const successCount = jobs.filter(j => j.status === 'success').length
  const failedCount = jobs.filter(j => j.status === 'failed').length
  const runningCount = jobs.filter(j => !j.status || j.status === 'running').length

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Job History</h1>

      {/* Quick Stats */}
      <div className="flex gap-4">
        <span className="px-3 py-1 rounded-full text-sm bg-green-50 text-green-700">
          {successCount} succeeded
        </span>
        <span className="px-3 py-1 rounded-full text-sm bg-red-50 text-red-700">
          {failedCount} failed
        </span>
        {runningCount > 0 && (
          <span className="px-3 py-1 rounded-full text-sm bg-yellow-50 text-yellow-700">
            {runningCount} running
          </span>
        )}
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Started</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Duration</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Metrics</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {jobs.map((job) => {
              const duration = job.finished_at && job.started_at
                ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
                : null

              return (
                <Fragment key={job.id}>
                  <tr
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === job.id ? null : job.id)}
                  >
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{job.job_name}</td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        job.status === 'success' ? 'bg-green-100 text-green-800' :
                        job.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {job.status || 'running'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(job.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {duration !== null ? formatDuration(duration) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {job.metrics ? (
                        <MetricsSummary metrics={job.metrics} />
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                  </tr>
                  {expandedId === job.id && (
                    <tr>
                      <td colSpan={5} className="px-4 py-4 bg-gray-50">
                        <div className="space-y-3">
                          {/* Full Metrics */}
                          {job.metrics && Object.keys(job.metrics).length > 0 && (
                            <div>
                              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Metrics</h4>
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                {Object.entries(job.metrics).map(([key, value]) => (
                                  <div key={key} className="bg-white rounded p-2 border border-gray-200">
                                    <p className="text-xs text-gray-400">{formatMetricKey(key)}</p>
                                    <p className="text-sm font-medium text-gray-900">
                                      {typeof value === 'number' ? value.toLocaleString() : String(value)}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Timestamps */}
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <p className="text-xs text-gray-400">Started</p>
                              <p className="text-sm text-gray-700">{new Date(job.started_at).toLocaleString()}</p>
                            </div>
                            {job.finished_at && (
                              <div>
                                <p className="text-xs text-gray-400">Finished</p>
                                <p className="text-sm text-gray-700">{new Date(job.finished_at).toLocaleString()}</p>
                              </div>
                            )}
                          </div>

                          {/* Error */}
                          {job.error_message && (
                            <div className="bg-red-50 rounded p-3 border border-red-200">
                              <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-1">Error</h4>
                              <pre className="text-sm text-red-600 whitespace-pre-wrap font-mono">{job.error_message}</pre>
                            </div>
                          )}

                          {!job.metrics && !job.error_message && (
                            <span className="text-sm text-gray-400">No additional details</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MetricsSummary({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics).slice(0, 3)
  return (
    <div className="flex gap-2">
      {entries.map(([key, value]) => (
        <span key={key} className="text-xs text-gray-500">
          {formatMetricKey(key)}: <span className="font-medium text-gray-700">{String(value)}</span>
        </span>
      ))}
      {Object.keys(metrics).length > 3 && (
        <span className="text-xs text-gray-400">+{Object.keys(metrics).length - 3}</span>
      )}
    </div>
  )
}

function formatMetricKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  return `${minutes}m ${remaining}s`
}
