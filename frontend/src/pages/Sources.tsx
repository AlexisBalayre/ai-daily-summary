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

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
        <button
          onClick={handleAdd}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
        >
          Add Source
        </button>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Name</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Type</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Enabled</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {sources.map((source) => (
              <tr key={source.id}>
                <td className="px-4 py-3 text-sm text-gray-900">{source.name}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{source.type}</td>
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
