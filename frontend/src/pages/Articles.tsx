import { useEffect, useState, Fragment } from 'react'
import { api } from '../api/client'
import type { Article } from '../api/types'

export default function Articles() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [aiFilter, setAiFilter] = useState<string>('')
  const [dupFilter, setDupFilter] = useState<string>('false')
  const [offset, setOffset] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const limit = 20

  useEffect(() => {
    async function fetchArticles() {
      setLoading(true)
      try {
        const data = await api.getArticles({
          q: search || undefined,
          category: category || undefined,
          is_ai_related: aiFilter === '' ? undefined : aiFilter === 'true',
          is_duplicate: dupFilter === '' ? undefined : dupFilter === 'true',
          exclude_source_type: 'github',
          limit,
          offset,
        })
        setArticles(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchArticles()
  }, [search, category, aiFilter, dupFilter, offset])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setOffset(0)
  }

  const resetFilters = () => {
    setSearch('')
    setCategory('')
    setAiFilter('')
    setDupFilter('false')
    setOffset(0)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Articles</h1>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title & content..."
              className="px-3 py-2 border border-gray-300 rounded-md text-sm w-64"
            />
          </form>
          <select
            value={category}
            onChange={(e) => { setCategory(e.target.value); setOffset(0) }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">All categories</option>
            <option value="AI/ML">AI/ML</option>
            <option value="Software Engineering">Software Engineering</option>
            <option value="Cloud">Cloud</option>
            <option value="Security">Security</option>
            <option value="Data">Data</option>
            <option value="DevOps">DevOps</option>
            <option value="Other">Other</option>
          </select>
          <select
            value={aiFilter}
            onChange={(e) => { setAiFilter(e.target.value); setOffset(0) }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">AI relevance: all</option>
            <option value="true">AI-related only</option>
            <option value="false">Non-AI only</option>
          </select>
          <select
            value={dupFilter}
            onChange={(e) => { setDupFilter(e.target.value); setOffset(0) }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">Duplicates: all</option>
            <option value="false">Unique only</option>
            <option value="true">Duplicates only</option>
          </select>
          <button
            onClick={resetFilters}
            className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
          >
            Reset
          </button>
        </div>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Title</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Source</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Category</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Date</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {articles.map((article) => (
              <Fragment key={article.id}>
                <tr
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === article.id ? null : article.id)}
                >
                  <td className="px-4 py-3 text-sm">
                    <div className="text-gray-900 font-medium">{article.title}</div>
                    {article.author && (
                      <div className="text-xs text-gray-400 mt-0.5">by {article.author}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{article.source_name || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex flex-wrap gap-1">
                      {article.category && (
                        <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">
                          {article.category}
                        </span>
                      )}
                      {article.is_ai_related && (
                        <span className="px-2 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700">
                          AI
                        </span>
                      )}
                      {article.is_duplicate && (
                        <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                          Duplicate
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {article.published_at ? new Date(article.published_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {article.enriched_at ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700">Enriched</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-500">Pending</span>
                    )}
                  </td>
                </tr>
                {expandedId === article.id && (
                  <tr>
                    <td colSpan={5} className="px-4 py-4 bg-gray-50">
                      <ArticleDetail article={article} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {!loading && articles.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                  No articles found
                </td>
              </tr>
            )}
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
        <span className="text-sm text-gray-500">
          Showing {articles.length > 0 ? offset + 1 : 0} - {offset + articles.length}
        </span>
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

function ArticleDetail({ article }: { article: Article }) {
  return (
    <div className="space-y-3 max-w-4xl">
      {/* Summary */}
      {article.summary && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Summary</h4>
          <p className="text-sm text-gray-700">{article.summary}</p>
        </div>
      )}

      {/* Content */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Content</h4>
        <p className="text-sm text-gray-600 whitespace-pre-wrap max-h-64 overflow-y-auto">
          {article.content}
        </p>
      </div>

      {/* Tags */}
      {article.tags && article.tags.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Tags</h4>
          <div className="flex flex-wrap gap-1">
            {article.tags.map((tag) => (
              <span key={tag} className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Metadata Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-gray-200">
        <MetaItem label="Topic" value={article.topic} />
        <MetaItem label="Category" value={article.category} />
        <MetaItem label="AI-Related" value={article.is_ai_related === true ? 'Yes' : article.is_ai_related === false ? 'No' : '-'} />
        <MetaItem label="Duplicate" value={article.is_duplicate ? `Yes (#${article.duplicate_of_id})` : 'No'} />
        <MetaItem label="Published" value={article.published_at ? new Date(article.published_at).toLocaleString() : '-'} />
        <MetaItem label="Ingested" value={article.ingested_at ? new Date(article.ingested_at).toLocaleString() : '-'} />
        <MetaItem label="Enriched" value={article.enriched_at ? new Date(article.enriched_at).toLocaleString() : '-'} />
        <MetaItem label="Source" value={article.source_name} />
      </div>

      {/* Link */}
      {article.url && (
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block text-indigo-600 text-sm hover:underline"
        >
          Open original article
        </a>
      )}
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm text-gray-700">{value || '-'}</p>
    </div>
  )
}
