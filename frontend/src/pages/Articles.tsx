import { useEffect, useState, Fragment } from 'react'
import { api } from '../api/client'
import type { Article } from '../api/types'

export default function Articles() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const limit = 20

  useEffect(() => {
    async function fetchArticles() {
      setLoading(true)
      try {
        const data = await api.getArticles({ q: search || undefined, limit, offset })
        setArticles(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchArticles()
  }, [search, offset])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setOffset(0)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Articles</h1>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700">
            Search
          </button>
        </form>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Title</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Source</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Topic</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {articles.map((article) => (
              <Fragment key={article.id}>
                <tr
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === article.id ? null : article.id)}
                >
                  <td className="px-4 py-3 text-sm text-gray-900">{article.title}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{article.source_name || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{article.topic || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {article.published_at ? new Date(article.published_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
                {expandedId === article.id && (
                  <tr>
                    <td colSpan={4} className="px-4 py-4 bg-gray-50">
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">{article.content}</p>
                      {article.url && (
                        <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 text-sm hover:underline mt-2 block">
                          Read more
                        </a>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-gray-500">Showing {offset + 1} - {offset + articles.length}</span>
        <button
          onClick={() => setOffset(offset + limit)}
          disabled={articles.length < limit}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
