export interface Article {
  id: number
  title: string
  content: string
  url?: string
  topic?: string
  published_at?: string
  source_name?: string
}

export interface Source {
  id: number
  type: string
  name: string
  config?: Record<string, unknown>
  enabled: boolean
}

export interface SourceCreate {
  type: string
  name: string
  config?: Record<string, unknown>
  enabled?: boolean
}

export interface Job {
  id: number
  job_name: string
  started_at: string
  finished_at?: string
  status?: string
  metrics?: Record<string, unknown>
  error_message?: string
}

export interface Summary {
  date: string
  summary_text?: string
  key_facts?: unknown
}

export interface SystemStatus {
  database: string
  total_articles: number
  articles_today: number
  active_sources: number
  last_job?: {
    name: string
    status: string
    started_at: string
  }
  next_runs?: Record<string, string>
}

export interface SourceTestResult {
  success: boolean
  message?: string
  preview?: {
    feed_title?: string
    entry_count?: number
    sample_titles?: string[]
    items_found?: number
  }
}

export interface WhitelistResponse {
  whitelist: string[]
}
