import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Source } from '../api/types'
import SourceModal from '../components/SourceModal'

export default function Sources() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<Source | undefined>()

  const fetchSources = async () => {
    try {
      const data = await api.getSources()
      setSources(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const handleToggle = async (source: Source) => {
    try {
      await api.toggleSource(source.id)
      fetchSources()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to toggle')
    }
  }

  const handleDelete = async (source: Source) => {
    if (!confirm(`Delete source "${source.name}"?`)) return
    try {
      await api.deleteSource(source.id)
      fetchSources()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    }
  }

  const handleEdit = (source: Source) => {
    setEditingSource(source)
    setModalOpen(true)
  }

  const handleAdd = () => {
    setEditingSource(undefined)
    setModalOpen(true)
  }

  const handleModalClose = () => {
    setModalOpen(false)
    setEditingSource(undefined)
  }

  const handleModalSave = () => {
    setModalOpen(false)
    setEditingSource(undefined)
    fetchSources()
  }

  // Group sources by type
  const byType = sources.reduce<Record<string, Source[]>>((acc, s) => {
    const key = s.type || 'other'
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})

  const typeLabels: Record<string, string> = {
    rss: 'RSS Feeds',
    newsletter: 'Newsletters',
    crawler: 'Web Crawlers',
    github: 'GitHub',
  }

  const typeColors: Record<string, string> = {
    rss: 'bg-orange-100 text-orange-800',
    newsletter: 'bg-blue-100 text-blue-800',
    crawler: 'bg-purple-100 text-purple-800',
    github: 'bg-gray-800 text-white',
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
          <p className="text-sm text-gray-500 mt-1">{sources.length} sources configured</p>
        </div>
        <button
          onClick={handleAdd}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
        >
          Add Source
        </button>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      {Object.entries(byType).map(([type, typeSources]) => (
        <div key={type}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[type] || 'bg-gray-100 text-gray-700'}`}>
              {typeLabels[type] || type}
            </span>
            <span className="text-xs text-gray-400">{typeSources.length}</span>
          </div>
          <div className="bg-white shadow rounded-lg overflow-hidden mb-4">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Details</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Created</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Enabled</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {typeSources.map((source) => (
                  <tr key={source.id}>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{source.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      <SourceDetails source={source} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {source.created_at ? new Date(source.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleToggle(source)}
                        className={`px-2 py-1 rounded text-xs ${
                          source.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {source.enabled ? 'Enabled' : 'Disabled'}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-right space-x-2">
                      <button
                        onClick={() => handleEdit(source)}
                        className="text-indigo-600 hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(source)}
                        className="text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {!loading && sources.length === 0 && (
        <div className="bg-white shadow rounded-lg p-8 text-center text-gray-400">
          No sources configured yet. Add an RSS feed, newsletter, or crawler to get started.
        </div>
      )}

      {modalOpen && (
        <SourceModal
          source={editingSource}
          onClose={handleModalClose}
          onSave={handleModalSave}
        />
      )}
    </div>
  )
}

function SourceDetails({ source }: { source: Source }) {
  const config = source.config
  if (!config) return <span className="text-gray-300">No config</span>

  switch (source.type) {
    case 'rss':
      return config.url ? (
        <span className="font-mono text-xs break-all">{String(config.url)}</span>
      ) : <span className="text-gray-300">-</span>

    case 'newsletter':
      return config.email ? (
        <span className="font-mono text-xs">{String(config.email)}</span>
      ) : <span className="text-gray-300">-</span>

    case 'crawler':
      return (
        <div className="space-y-0.5">
          {config.url ? <div className="font-mono text-xs break-all">{String(config.url)}</div> : null}
          {config.selector ? <div className="text-xs text-gray-400">selector: {String(config.selector)}</div> : null}
        </div>
      )

    case 'github':
      return config.language ? (
        <span className="text-xs">{String(config.language)}</span>
      ) : <span className="text-gray-300">-</span>

    default: {
      const entries = Object.entries(config)
      if (entries.length === 0) return <span className="text-gray-300">-</span>
      return (
        <div className="space-y-0.5">
          {entries.slice(0, 3).map(([k, v]) => (
            <div key={k} className="text-xs">
              <span className="text-gray-400">{k}:</span> {String(v)}
            </div>
          ))}
        </div>
      )
    }
  }
}
