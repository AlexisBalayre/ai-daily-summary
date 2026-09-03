import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Release } from '../api/types'

const WINDOWS = [7, 14, 30] as const

export default function Releases() {
  const [releases, setReleases] = useState<Release[]>([])
  const [days, setDays] = useState<number>(7)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Loading flips on when the window changes (see selectWindow), never inside the effect.
  const selectWindow = (d: number) => {
    setDays(d)
    setLoading(true)
  }

  useEffect(() => {
    api
      .getReleases(days)
      .then(setReleases)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [days])

  if (error) return <div className="text-red-500">Error: {error}</div>

  // Group by ingestion day for a timeline reading.
  const byDay = new Map<string, Release[]>()
  for (const r of releases) {
    const day = r.ingested_at ? r.ingested_at.slice(0, 10) : 'unknown'
    byDay.set(day, [...(byDay.get(day) ?? []), r])
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Release Radar</h1>
        <div className="flex rounded-md shadow-sm">
          {WINDOWS.map((w) => (
            <button
              key={w}
              onClick={() => selectWindow(w)}
              className={`px-3 py-1.5 text-sm font-medium border first:rounded-l-md last:rounded-r-md -ml-px first:ml-0 ${
                days === w
                  ? 'bg-gray-900 text-white border-gray-900'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>
      <p className="text-sm text-gray-500">
        New AI model announcements detected by enrichment ({releases.length} in the last {days}{' '}
        days). Fresh releases also arrive as instant email alerts.
      </p>

      {loading ? (
        <div className="text-gray-500">Loading...</div>
      ) : (
        [...byDay.entries()].map(([day, items]) => (
          <div key={day}>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
              {day === 'unknown' ? 'Unknown date' : new Date(day).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
            </h2>
            <div className="space-y-2 mb-6">
              {items.map((r) => (
                <div key={r.id} className="bg-white shadow rounded-lg p-4">
                  <div className="flex items-start justify-between gap-3">
                    <a
                      href={r.url ?? '#'}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-semibold text-gray-900 hover:text-blue-600"
                    >
                      🚀 {r.title}
                    </a>
                    {r.source_name && (
                      <span className="shrink-0 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700">
                        {r.source_name}
                      </span>
                    )}
                  </div>
                  {r.summary && <p className="mt-1.5 text-sm text-gray-600">{r.summary}</p>}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
