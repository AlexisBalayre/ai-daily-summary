import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function Whitelist() {
  const [emails, setEmails] = useState<string[]>([])
  const [newEmail, setNewEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    loadWhitelist()
  }, [])

  async function loadWhitelist() {
    try {
      setLoading(true)
      const data = await api.getWhitelist()
      setEmails(data.whitelist)
      setError(null)
    } catch {
      setError('Failed to load whitelist')
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!newEmail.trim()) return

    try {
      setAdding(true)
      const data = await api.addToWhitelist(newEmail.trim())
      setEmails(data.whitelist)
      setNewEmail('')
      setError(null)
    } catch {
      setError('Failed to add email')
    } finally {
      setAdding(false)
    }
  }

  async function handleRemove(email: string) {
    if (!confirm(`Remove ${email} from whitelist?`)) return

    try {
      await api.removeFromWhitelist(email)
      setEmails(emails.filter(e => e.toLowerCase() !== email.toLowerCase()))
      setError(null)
    } catch {
      setError('Failed to remove email')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Newsletter Whitelist</h1>
        <span className="text-sm text-gray-500">{emails.length} senders</span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <form onSubmit={handleAdd} className="flex gap-3">
        <input
          type="email"
          value={newEmail}
          onChange={e => setNewEmail(e.target.value)}
          placeholder="sender@newsletter.com"
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          type="submit"
          disabled={adding || !newEmail.trim()}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {adding ? 'Adding...' : 'Add Sender'}
        </button>
      </form>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {emails.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No whitelisted senders. Add newsletter sender emails above.
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {emails.map(email => (
              <li key={email} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50">
                <span className="text-gray-900 font-mono text-sm">{email}</span>
                <button
                  onClick={() => handleRemove(email)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-sm text-gray-500">
        Only emails from whitelisted senders will be processed by the newsletter ingestion pipeline.
      </p>
    </div>
  )
}
