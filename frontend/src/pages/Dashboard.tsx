import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { SystemStatus, Job } from '../api/types'

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [statusData, jobsData] = await Promise.all([
          api.getStatus(),
          api.getJobs(5),
        ])
        setStatus(statusData)
        setRecentJobs(jobsData)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>
  if (!status) return null

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        <StatCard title="Database" value={status.database} />
        <StatCard title="Total Articles" value={status.total_articles.toString()} />
        <StatCard title="Articles Today" value={status.articles_today.toString()} />
        <StatCard title="Active Sources" value={status.active_sources.toString()} />
      </div>

      {/* Last Job */}
      {status.last_job && (
        <div className="bg-white shadow rounded-lg p-4">
          <h2 className="text-lg font-medium text-gray-900 mb-2">Last Job</h2>
          <p className="text-gray-600">
            <span className="font-medium">{status.last_job.name}</span>
            {' - '}
            <span className={status.last_job.status === 'success' ? 'text-green-600' : 'text-red-600'}>
              {status.last_job.status}
            </span>
            {' at '}
            {new Date(status.last_job.started_at).toLocaleString()}
          </p>
        </div>
      )}

      {/* Recent Jobs */}
      <div className="bg-white shadow rounded-lg p-4">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Jobs</h2>
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Started</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {recentJobs.map((job) => (
              <tr key={job.id}>
                <td className="px-4 py-2 text-sm text-gray-900">{job.job_name}</td>
                <td className="px-4 py-2 text-sm">
                  <span className={`px-2 py-1 rounded text-xs ${
                    job.status === 'success' ? 'bg-green-100 text-green-800' :
                    job.status === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {job.status || 'running'}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-500">
                  {new Date(job.started_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="bg-white shadow rounded-lg p-4">
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  )
}
