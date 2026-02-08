import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Summary } from '../api/types'

export default function Summaries() {
  const [summaries, setSummaries] = useState<Summary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedDate, setExpandedDate] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const limit = 20

  useEffect(() => {
    async function fetchSummaries() {
      setLoading(true)
      try {
        const data = await api.getSummaries({ limit, offset })
        setSummaries(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchSummaries()
  }, [offset])

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Daily Summaries</h1>

      {summaries.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-8 text-center text-gray-400">
          No summaries generated yet. Summaries are created daily by the newsletter job.
        </div>
      ) : (
        <div className="space-y-4">
          {summaries.map((summary) => {
            const isExpanded = expandedDate === summary.date
            const dateStr = new Date(summary.date).toLocaleDateString(undefined, {
              weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
            })

            return (
              <div key={summary.date} className="bg-white shadow rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedDate(isExpanded ? null : summary.date)}
                  className="w-full px-5 py-4 flex justify-between items-center hover:bg-gray-50 text-left"
                >
                  <div>
                    <h3 className="text-base font-medium text-gray-900">{dateStr}</h3>
                    <div className="flex gap-3 mt-1">
                      {summary.article_ids && (
                        <span className="text-xs text-gray-500">
                          {summary.article_ids.length} articles
                        </span>
                      )}
                      {summary.created_at && (
                        <span className="text-xs text-gray-400">
                          Generated {new Date(summary.created_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="text-gray-400 text-sm">{isExpanded ? 'Collapse' : 'Expand'}</span>
                </button>

                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-gray-100">
                    {/* Summary Text */}
                    {summary.summary_text ? (
                      <div className="mt-4">
                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                          Summary
                        </h4>
                        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                          {summary.summary_text}
                        </div>
                      </div>
                    ) : (
                      <p className="mt-4 text-sm text-gray-400">No summary text available</p>
                    )}

                    {/* Key Facts */}
                    {summary.key_facts && (
                      <div className="mt-4">
                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                          Key Facts
                        </h4>
                        <KeyFacts data={summary.key_facts} />
                      </div>
                    )}

                    {/* Article IDs */}
                    {summary.article_ids && summary.article_ids.length > 0 && (
                      <div className="mt-4">
                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                          Article IDs
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {summary.article_ids.map((id) => (
                            <span
                              key={id}
                              className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600 font-mono"
                            >
                              #{id}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {summaries.length > 0 && (
        <div className="flex justify-between items-center">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Showing {offset + 1} - {offset + summaries.length}
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={summaries.length < limit}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

function KeyFacts({ data }: { data: Record<string, unknown> | unknown[] }) {
  if (Array.isArray(data)) {
    return (
      <ul className="list-disc list-inside space-y-1">
        {data.map((fact, i) => (
          <li key={i} className="text-sm text-gray-700">
            {typeof fact === 'string' ? fact : JSON.stringify(fact)}
          </li>
        ))}
      </ul>
    )
  }

  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt className="text-xs text-gray-500">{key}</dt>
          <dd className="text-sm text-gray-700">
            {typeof value === 'string' ? value : JSON.stringify(value)}
          </dd>
        </div>
      ))}
    </dl>
  )
}
