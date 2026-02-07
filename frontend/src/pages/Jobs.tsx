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

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Job History</h1>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Started</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Duration</th>
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
                    <td className="px-4 py-3 text-sm text-gray-900">{job.job_name}</td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`px-2 py-1 rounded text-xs ${
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
                      {duration !== null ? `${duration}s` : '-'}
                    </td>
                  </tr>
                  {expandedId === job.id && (
                    <tr>
                      <td colSpan={4} className="px-4 py-4 bg-gray-50">
                        {job.metrics && (
                          <div className="mb-2">
                            <span className="font-medium text-sm text-gray-700">Metrics: </span>
                            <span className="text-sm text-gray-600">{JSON.stringify(job.metrics)}</span>
                          </div>
                        )}
                        {job.error_message && (
                          <div className="text-sm text-red-600">
                            <span className="font-medium">Error: </span>
                            {job.error_message}
                          </div>
                        )}
                        {!job.metrics && !job.error_message && (
                          <span className="text-sm text-gray-500">No additional details</span>
                        )}
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
