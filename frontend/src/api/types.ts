export interface Article {
  id: number
  title: string
  content: string
  url?: string
  author?: string
  topic?: string
  tags?: string[]
  published_at?: string
  ingested_at?: string
  source_name?: string
  summary?: string
  category?: string
  is_ai_related?: boolean
  enriched_at?: string
  is_duplicate: boolean
  duplicate_of_id?: number
}

export interface Source {
  id: number
  type: string
  name: string
  config?: Record<string, unknown>
  enabled: boolean
  created_at?: string
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
  key_facts?: Record<string, unknown> | unknown[]
  article_ids?: number[]
  created_at?: string
}

export interface SystemStatus {
  database: string
  total_articles: number
  articles_today: number
  active_sources: number
  enriched_articles: number
  ai_related_articles: number
  duplicate_articles: number
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

export interface Release {
  id: number
  title: string
  url: string | null
  summary: string | null
  source_name: string | null
  ingested_at: string | null
}

export interface LeaderboardSummary {
  board: string
  captured_at: string | null
  row_count: number
  top: string[]
}

export interface LeaderboardRow {
  name: string
  rank: number
  metrics?: Record<string, number>
}

export interface LeaderboardDetail {
  board: string
  captured_at: string
  row_count: number
  rows: LeaderboardRow[]
}

export interface BriefingInfo {
  date: string
  size_bytes: number
  has_script: boolean
}
