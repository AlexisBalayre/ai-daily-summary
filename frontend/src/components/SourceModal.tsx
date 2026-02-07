import { useState } from 'react'
import { Dialog } from '@headlessui/react'
import { api } from '../api/client'
import type { Source, SourceCreate, SourceTestResult } from '../api/types'

interface Props {
  source?: Source
  onClose: () => void
  onSave: () => void
}

export default function SourceModal({ source, onClose, onSave }: Props) {
  const [type, setType] = useState(source?.type || 'rss')
  const [name, setName] = useState(source?.name || '')
  const [config, setConfig] = useState(JSON.stringify(source?.config || {}, null, 2))
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<SourceTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const configObj = JSON.parse(config)
      const result = await api.testSource({ type, name, config: configObj })
      setTestResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const configObj = JSON.parse(config)
      const data: SourceCreate = { type, name, config: configObj }
      if (source) {
        await api.updateSource(source.id, data)
      } else {
        await api.createSource(data)
      }
      onSave()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="bg-white rounded-lg p-6 w-full max-w-md">
          <Dialog.Title className="text-lg font-medium text-gray-900 mb-4">
            {source ? 'Edit Source' : 'Add Source'}
          </Dialog.Title>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                disabled={!!source}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="rss">RSS</option>
                <option value="newsletter">Newsletter</option>
                <option value="crawler">Crawler</option>
                <option value="github">GitHub</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Config (JSON)</label>
              <textarea
                value={config}
                onChange={(e) => setConfig(e.target.value)}
                rows={5}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
              />
            </div>

            {testResult && (
              <div className={`p-3 rounded text-sm ${testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
                {testResult.success ? 'Test passed!' : testResult.message}
                {testResult.preview && (
                  <pre className="mt-2 text-xs">{JSON.stringify(testResult.preview, null, 2)}</pre>
                )}
              </div>
            )}

            {error && <div className="text-red-600 text-sm">{error}</div>}
          </div>

          <div className="mt-6 flex justify-between">
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
            >
              {testing ? 'Testing...' : 'Test'}
            </button>
            <div className="flex gap-2">
              <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md text-sm">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Dialog.Panel>
      </div>
    </Dialog>
  )
}
