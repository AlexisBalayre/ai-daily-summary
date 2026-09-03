import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Article, SystemStatus, Job, Summary, Release, LeaderboardSummary } from '../api/types'

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[]>([])
  const [latestSummary, setLatestSummary] = useState<Summary | null>(null)
  const [githubRepos, setGithubRepos] = useState<Article[]>([])
  const [releases, setReleases] = useState<Release[]>([])
  const [boards, setBoards] = useState<LeaderboardSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [statusData, jobsData, summariesData, reposData, releasesData, boardsData] =
          await Promise.all([
            api.getStatus(),
            api.getJobs(5),
            api.getSummaries({ limit: 1 }),
            api.getArticles({ source_type: 'github', is_duplicate: false, limit: 20 }),
            api.getReleases(7).catch(() => [] as Release[]),
            api.getLeaderboards().catch(() => [] as LeaderboardSummary[]),
          ])
        setStatus(statusData)
        setRecentJobs(jobsData)
        if (summariesData.length > 0) setLatestSummary(summariesData[0])
        setGithubRepos(reposData)
        setReleases(releasesData)
        setBoards(boardsData.filter((b) => b.row_count > 0))
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

  const enrichedPct = status.total_articles > 0
    ? Math.round((status.enriched_articles / status.total_articles) * 100)
    : 0

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Primary Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Articles"
          value={status.total_articles.toLocaleString()}
          subtitle={`${status.articles_today} ingested today`}
          color="indigo"
        />
        <StatCard
          title="Active Sources"
          value={status.active_sources.toString()}
          subtitle="Enabled sources"
          color="blue"
        />
        <StatCard
          title="AI-Related"
          value={status.ai_related_articles.toLocaleString()}
          subtitle={`of ${status.enriched_articles} enriched`}
          color="emerald"
        />
        <StatCard
          title="Duplicates"
          value={status.duplicate_articles.toLocaleString()}
          subtitle={`${enrichedPct}% enriched`}
          color="amber"
        />
      </div>

      {/* Release Radar + Leaderboard highlights */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="bg-white shadow rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium text-gray-900">🚀 Release Radar (7d)</h2>
            <Link to="/releases" className="text-sm text-indigo-600 hover:underline">View all</Link>
          </div>
          {releases.length === 0 ? (
            <p className="text-sm text-gray-400">No model releases detected this week</p>
          ) : (
            <ul className="space-y-2">
              {releases.slice(0, 6).map((r) => (
                <li key={r.id} className="flex items-start justify-between gap-2">
                  <a
                    href={r.url ?? '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-gray-800 hover:text-blue-600 line-clamp-1"
                  >
                    {r.title}
                  </a>
                  {r.source_name && (
                    <span className="shrink-0 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700">
                      {r.source_name}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white shadow rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium text-gray-900">📊 Leaderboards</h2>
            <Link to="/leaderboards" className="text-sm text-indigo-600 hover:underline">View all</Link>
          </div>
          {boards.length === 0 ? (
            <p className="text-sm text-gray-400">No snapshots captured yet</p>
          ) : (
            <div className="space-y-3">
              {boards.slice(0, 4).map((b) => (
                <div key={b.board} className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium text-gray-700">{b.board}</span>
                  <span className="text-sm text-gray-500 truncate">
                    {b.top.slice(0, 3).join(' · ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Last Job + Next Runs */}
        <div className="bg-white shadow rounded-lg p-5">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Schedule</h2>
          {status.last_job && (
            <div className="mb-4 pb-4 border-b border-gray-100">
              <p className="text-sm text-gray-500 mb-1">Last job</p>
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900">{status.last_job.name}</span>
                <StatusBadge status={status.last_job.status} />
                <span className="text-sm text-gray-400">
                  {new Date(status.last_job.started_at).toLocaleString()}
                </span>
              </div>
            </div>
          )}
          {status.next_runs && Object.keys(status.next_runs).length > 0 && (
            <div>
              <p className="text-sm text-gray-500 mb-2">Next scheduled runs</p>
              <div className="space-y-2">
                {Object.entries(status.next_runs).map(([job, time]) => (
                  <div key={job} className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">{job}</span>
                    <span className="text-sm text-gray-500">{new Date(time).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!status.last_job && (!status.next_runs || Object.keys(status.next_runs).length === 0) && (
            <p className="text-sm text-gray-400">No job data available</p>
          )}
        </div>

        {/* Latest Summary */}
        <div className="bg-white shadow rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium text-gray-900">Latest Summary</h2>
            <Link to="/summaries" className="text-sm text-indigo-600 hover:underline">View all</Link>
          </div>
          {latestSummary ? (
            <div>
              <p className="text-sm text-gray-500 mb-2">
                {new Date(latestSummary.date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
              {latestSummary.summary_text ? (
                <p className="text-sm text-gray-700 line-clamp-6 whitespace-pre-wrap">
                  {latestSummary.summary_text.slice(0, 500)}{latestSummary.summary_text.length > 500 ? '...' : ''}
                </p>
              ) : (
                <p className="text-sm text-gray-400">No summary text</p>
              )}
              {latestSummary.article_ids && (
                <p className="mt-2 text-xs text-gray-400">{latestSummary.article_ids.length} articles included</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No summaries generated yet</p>
          )}
        </div>
      </div>

      {/* GitHub Trending */}
      {githubRepos.length > 0 && (
        <div className="bg-white shadow rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-medium text-gray-900">GitHub Trending</h2>
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-800 text-white">
                {githubRepos.length} repos
              </span>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {githubRepos.map((repo) => (
              <RepoCard key={repo.id} repo={repo} />
            ))}
          </div>
        </div>
      )}

      {/* Recent Jobs */}
      <div className="bg-white shadow rounded-lg p-5">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium text-gray-900">Recent Jobs</h2>
          <Link to="/jobs" className="text-sm text-indigo-600 hover:underline">View all</Link>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Started</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {recentJobs.map((job) => {
              const duration = job.finished_at && job.started_at
                ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
                : null
              return (
                <tr key={job.id}>
                  <td className="px-4 py-2 text-sm text-gray-900">{job.job_name}</td>
                  <td className="px-4 py-2 text-sm">
                    <StatusBadge status={job.status || 'running'} />
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">
                    {new Date(job.started_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">
                    {duration !== null ? `${duration}s` : '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Database Status */}
      <div className="text-sm text-gray-400 flex items-center gap-2">
        <span className={`inline-block w-2 h-2 rounded-full ${status.database === 'connected' ? 'bg-green-400' : 'bg-red-400'}`} />
        Database {status.database}
      </div>
    </div>
  )
}

function StatCard({ title, value, subtitle, color }: { title: string; value: string; subtitle?: string; color: string }) {
  const colorClasses: Record<string, string> = {
    indigo: 'border-l-indigo-500',
    blue: 'border-l-blue-500',
    emerald: 'border-l-emerald-500',
    amber: 'border-l-amber-500',
  }
  return (
    <div className={`bg-white shadow rounded-lg p-4 border-l-4 ${colorClasses[color] || 'border-l-gray-300'}`}>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
      {subtitle && <p className="mt-1 text-xs text-gray-400">{subtitle}</p>}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'success' ? 'bg-green-100 text-green-800' :
    status === 'failed' ? 'bg-red-100 text-red-800' :
    'bg-yellow-100 text-yellow-800'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

function RepoCard({ repo }: { repo: Article }) {
  // Parse content: "description\n\nLanguage: X\nStars: Y\nForks: Z"
  const lines = repo.content.split('\n')
  const description = lines[0] || ''
  const meta: Record<string, string> = {}
  for (const line of lines) {
    const match = line.match(/^(Language|Stars|Forks):\s*(.+)/)
    if (match) meta[match[1]] = match[2]
  }

  const langColors: Record<string, string> = {
    Python: 'bg-blue-100 text-blue-800',
    TypeScript: 'bg-blue-100 text-blue-700',
    JavaScript: 'bg-yellow-100 text-yellow-800',
    Rust: 'bg-orange-100 text-orange-800',
    Go: 'bg-cyan-100 text-cyan-800',
    Java: 'bg-red-100 text-red-700',
    'C++': 'bg-pink-100 text-pink-800',
    C: 'bg-gray-100 text-gray-800',
    Swift: 'bg-orange-100 text-orange-700',
    Kotlin: 'bg-purple-100 text-purple-800',
  }
  const lang = meta['Language'] || 'Unknown'
  const langCls = langColors[lang] || 'bg-gray-100 text-gray-700'

  return (
    <a
      href={repo.url || '#'}
      target="_blank"
      rel="noopener noreferrer"
      className="block border border-gray-200 rounded-lg p-3 hover:border-gray-400 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 truncate">{repo.title}</h3>
      </div>
      {description && (
        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{description}</p>
      )}
      <div className="flex items-center gap-3 mt-2">
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${langCls}`}>{lang}</span>
        {meta['Stars'] && (
          <span className="text-xs text-gray-500">{meta['Stars']} stars</span>
        )}
        {meta['Forks'] && (
          <span className="text-xs text-gray-500">{meta['Forks']} forks</span>
        )}
      </div>
    </a>
  )
}
