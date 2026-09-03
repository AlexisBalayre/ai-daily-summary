import type { Article, Source, SourceCreate, Job, Summary, SystemStatus, SourceTestResult, WhitelistResponse, Release, LeaderboardSummary, LeaderboardDetail, BriefingInfo } from './types'

const API_BASE = '/api/v1'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}

export const api = {
  // Status
  getStatus: () => fetchJSON<SystemStatus>(`${API_BASE}/status`),

  // Articles
  getArticles: (params?: {
    q?: string
    topic?: string
    category?: string
    is_ai_related?: boolean
    is_duplicate?: boolean
    source_type?: string
    exclude_source_type?: string
    from?: string
    to?: string
    limit?: number
    offset?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.q) searchParams.set('q', params.q)
    if (params?.topic) searchParams.set('topic', params.topic)
    if (params?.category) searchParams.set('category', params.category)
    if (params?.is_ai_related !== undefined) searchParams.set('is_ai_related', params.is_ai_related.toString())
    if (params?.is_duplicate !== undefined) searchParams.set('is_duplicate', params.is_duplicate.toString())
    if (params?.source_type) searchParams.set('source_type', params.source_type)
    if (params?.exclude_source_type) searchParams.set('exclude_source_type', params.exclude_source_type)
    if (params?.from) searchParams.set('from', params.from)
    if (params?.to) searchParams.set('to', params.to)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return fetchJSON<Article[]>(`${API_BASE}/articles${query ? `?${query}` : ''}`)
  },

  getArticle: (id: number) => fetchJSON<Article>(`${API_BASE}/articles/${id}`),

  // Sources
  getSources: () => fetchJSON<Source[]>(`${API_BASE}/sources`),
  getSource: (id: number) => fetchJSON<Source>(`${API_BASE}/sources/${id}`),
  createSource: (source: SourceCreate) =>
    fetchJSON<Source>(`${API_BASE}/sources`, {
      method: 'POST',
      body: JSON.stringify(source),
    }),
  updateSource: (id: number, source: Partial<SourceCreate>) =>
    fetchJSON<Source>(`${API_BASE}/sources/${id}`, {
      method: 'PUT',
      body: JSON.stringify(source),
    }),
  deleteSource: (id: number) =>
    fetchJSON<void>(`${API_BASE}/sources/${id}`, { method: 'DELETE' }),
  toggleSource: (id: number) =>
    fetchJSON<Source>(`${API_BASE}/sources/${id}/toggle`, { method: 'PATCH' }),
  testSource: (source: SourceCreate) =>
    fetchJSON<SourceTestResult>(`${API_BASE}/sources/test`, {
      method: 'POST',
      body: JSON.stringify(source),
    }),

  // Jobs
  getJobs: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : ''
    return fetchJSON<Job[]>(`${API_BASE}/jobs${query}`)
  },

  // Summaries
  getSummaries: (params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return fetchJSON<Summary[]>(`${API_BASE}/summaries${query ? `?${query}` : ''}`)
  },

  // Releases & leaderboards & briefings
  getReleases: (days = 7) => fetchJSON<Release[]>(`${API_BASE}/releases?days=${days}`),
  getLeaderboards: () => fetchJSON<LeaderboardSummary[]>(`${API_BASE}/leaderboards`),
  getLeaderboard: (board: string, limit = 50) =>
    fetchJSON<LeaderboardDetail>(`${API_BASE}/leaderboards/${board}?limit=${limit}`),
  getBriefings: () => fetchJSON<BriefingInfo[]>(`${API_BASE}/briefings`),
  getBriefingScript: (day: string) =>
    fetchJSON<{ date: string; script: string }>(`${API_BASE}/briefings/${day}/script`),
  triggerJob: (job: string) =>
    fetchJSON<{ job: string; status: string }>(`${API_BASE}/jobs/${job}/trigger`, { method: 'POST' }),

  // Whitelist
  getWhitelist: () => fetchJSON<WhitelistResponse>(`${API_BASE}/whitelist`),
  addToWhitelist: (email: string) =>
    fetchJSON<WhitelistResponse>(`${API_BASE}/whitelist`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  removeFromWhitelist: (email: string) =>
    fetchJSON<void>(`${API_BASE}/whitelist/${encodeURIComponent(email)}`, {
      method: 'DELETE',
    }),
}
