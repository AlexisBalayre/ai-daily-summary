import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { LeaderboardSummary, LeaderboardDetail } from '../api/types'

const BOARD_LABELS: Record<string, string> = {
  'arena-text': 'Arena — Text',
  'arena-agent': 'Arena — Agent',
  'hf-open-llm': 'HF Open LLM Leaderboard',
  'aa-tts-models': 'Artificial Analysis — TTS',
  'aa-stt-streaming': 'Artificial Analysis — STT Streaming',
  'aa-speech-to-speech': 'Artificial Analysis — Speech-to-Speech',
  'coval-tts': 'Coval — TTS',
  'coval-stt': 'Coval — STT',
}

export default function Leaderboards() {
  const [boards, setBoards] = useState<LeaderboardSummary[]>([])
  const [detail, setDetail] = useState<LeaderboardDetail | null>(null)
  const [openBoard, setOpenBoard] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getLeaderboards()
      .then(setBoards)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  async function openDetail(board: string) {
    if (openBoard === board) {
      setOpenBoard(null)
      setDetail(null)
      return
    }
    setOpenBoard(board)
    setDetail(null)
    try {
      setDetail(await api.getLeaderboard(board, 100))
    } catch {
      setDetail(null)
    }
  }

  async function refreshAll() {
    setRefreshing(true)
    try {
      await api.triggerJob('leaderboards')
    } finally {
      setTimeout(() => setRefreshing(false), 3000)
    }
  }

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Leaderboards</h1>
        <button
          onClick={refreshAll}
          disabled={refreshing}
          className="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {refreshing ? 'Capture started…' : 'Re-capture now'}
        </button>
      </div>
      <p className="text-sm text-gray-500">
        Daily snapshots of external model leaderboards. Changes (new models, rank moves) trigger an
        email digest.
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {boards.map((b) => (
          <div key={b.board} className="bg-white shadow rounded-lg">
            <button
              onClick={() => openDetail(b.board)}
              className="w-full text-left p-5 hover:bg-gray-50 rounded-lg"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-gray-900">
                  {BOARD_LABELS[b.board] ?? b.board}
                </h2>
                <span className="text-xs text-gray-400">
                  {b.captured_at ? new Date(b.captured_at).toLocaleDateString() : 'no snapshot yet'}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-500">{b.row_count} models tracked</p>
              {b.top.length > 0 && (
                <ol className="mt-3 space-y-1">
                  {b.top.slice(0, 5).map((name, i) => (
                    <li key={name} className="text-sm text-gray-700">
                      <span className="inline-block w-6 text-gray-400 tabular-nums">#{i + 1}</span>
                      {name}
                    </li>
                  ))}
                </ol>
              )}
            </button>

            {openBoard === b.board && (
              <div className="border-t border-gray-100 max-h-96 overflow-y-auto">
                {!detail ? (
                  <div className="p-4 text-sm text-gray-400">Loading…</div>
                ) : (
                  <table className="min-w-full divide-y divide-gray-100">
                    <tbody className="divide-y divide-gray-50">
                      {detail.rows.map((r) => (
                        <tr key={`${r.rank}-${r.name}`}>
                          <td className="px-4 py-1.5 text-sm text-gray-400 tabular-nums w-12">
                            #{r.rank}
                          </td>
                          <td className="px-2 py-1.5 text-sm text-gray-800">{r.name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
