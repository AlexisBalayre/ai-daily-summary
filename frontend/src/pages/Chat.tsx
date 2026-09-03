import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Tailwind's preflight strips list/heading styles; restore them inside bubbles.
const MD_COMPONENTS = {
  p: (props: object) => <p className="my-1.5 first:mt-0 last:mb-0" {...props} />,
  ul: (props: object) => <ul className="my-1.5 ml-5 list-disc space-y-1" {...props} />,
  ol: (props: object) => <ol className="my-1.5 ml-5 list-decimal space-y-1" {...props} />,
  li: (props: object) => <li className="[&>p]:my-0" {...props} />,
  strong: (props: object) => <strong className="font-semibold text-gray-900" {...props} />,
  a: (props: object) => (
    <a className="text-blue-600 hover:underline" target="_blank" rel="noreferrer" {...props} />
  ),
  h1: (props: object) => <h3 className="font-semibold text-gray-900 mt-3 mb-1" {...props} />,
  h2: (props: object) => <h3 className="font-semibold text-gray-900 mt-3 mb-1" {...props} />,
  h3: (props: object) => <h3 className="font-semibold text-gray-900 mt-3 mb-1" {...props} />,
  code: (props: object) => (
    <code className="px-1 py-0.5 rounded bg-gray-100 text-[13px] font-mono" {...props} />
  ),
  pre: (props: object) => (
    <pre className="my-2 p-3 rounded bg-gray-100 text-[13px] overflow-x-auto" {...props} />
  ),
  table: (props: object) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full text-[13px] border-collapse [&_td]:border [&_td]:border-gray-200 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-gray-200 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-gray-50" {...props} />
    </div>
  ),
}

interface Msg {
  role: 'user' | 'assistant'
  content: string
  tools?: string[]
}

const SUGGESTIONS = [
  'What model releases came out this week?',
  'Who leads the arena text leaderboard?',
  'Summarize today’s AI news',
  'Which TTS model has the lowest latency on Coval?',
]

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function send(text?: string) {
    const question = (text ?? input).trim()
    if (!question || busy) return
    setError(null)
    setInput('')
    const history = [...messages, { role: 'user' as const, content: question }]
    setMessages(history)
    setBusy(true)
    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data: { reply: string; tools_used: string[] } = await res.json()
      setMessages((m) => [...m, { role: 'assistant', content: data.reply, tools: data.tools_used }])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
      setMessages((m) => m.slice(0, -1))
      setInput(question)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Chat</h1>
      <p className="text-sm text-gray-500 mb-4">
        Ask about your articles, model releases, leaderboards, and pipeline. Answers are grounded
        in your data.
      </p>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-6">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="text-left text-sm p-3 bg-white shadow rounded-lg text-gray-600 hover:bg-gray-50"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                m.role === 'user'
                  ? 'max-w-[85%] bg-gray-900 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm whitespace-pre-wrap'
                  : 'max-w-[85%] bg-white shadow rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-800'
              }
            >
              {m.role === 'assistant' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                  {m.content}
                </ReactMarkdown>
              ) : (
                m.content
              )}
              {m.tools && m.tools.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {[...new Set(m.tools)].map((t) => (
                    <span
                      key={t}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-600"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex justify-start">
            <div className="bg-white shadow rounded-2xl rounded-bl-sm px-4 py-3">
              <span className="inline-flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce" />
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce [animation-delay:120ms]" />
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce [animation-delay:240ms]" />
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-sm text-red-500 mt-2">{error}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="mt-3 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your AI news…"
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="px-4 py-2.5 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  )
}
