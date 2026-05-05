import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Bot, Check, X } from 'lucide-react'

const API = 'http://localhost:8000'
const UNLOCK_THRESHOLD = 0.7
const TOPIC_SUBTOPICS = {
  stack: [
    { id: 'stack_introduction', title: 'Introduction & Concept' },
    { id: 'stack_push', title: 'Push Operation' },
    { id: 'stack_pop', title: 'Pop Operation' },
    { id: 'stack_peek', title: 'Peek Operation' },
    { id: 'stack_isempty_isfull', title: 'isEmpty / isFull' },
    { id: 'stack_array', title: 'Stack using Array' },
    { id: 'stack_linked_list', title: 'Stack using Linked List' },
    { id: 'stack_applications', title: 'Applications (expression evaluation, backtracking)' },
  ],
}

const normalize = (s = '') => s.trim().toLowerCase().replace(/\s+/g, ' ')

function masteryPillClass(mastery) {
  if (mastery < 0.4) return 'bg-red-800'
  if (mastery <= 0.7) return 'bg-yellow-700'
  return 'bg-green-700'
}

function ThinkingState() {
  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
      <div className="mb-2 flex gap-2 text-teal-400">
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" style={{ animationDelay: '0.12s' }} />
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" style={{ animationDelay: '0.24s' }} />
      </div>
      <p className="text-sm text-gray-300">Analyzing your learning state...</p>
    </div>
  )
}

function TutorMarkdown({ text, streaming }) {
  return (
    <div className="prose prose-invert max-w-none prose-p:my-2 prose-li:my-1">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            if (!inline) {
              return (
                <SyntaxHighlighter
                  {...props}
                  style={oneDark}
                  language={match?.[1] || 'python'}
                  PreTag="div"
                  customStyle={{ borderRadius: '0.9rem', border: '1px solid rgba(148,163,184,0.25)' }}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              )
            }
            return <code className={className} {...props}>{children}</code>
          },
        }}
      >
        {text}
      </ReactMarkdown>
      {streaming && <span className="ml-1 inline-block h-4 w-[2px] animate-pulse bg-teal-400 align-middle" />}
    </div>
  )
}

function ScoreRing({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? '#14b8a6' : pct >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative h-20 w-20">
      <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
        <path d="M18 2.5a15.5 15.5 0 1 1 0 31a15.5 15.5 0 1 1 0-31" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
        <path d="M18 2.5a15.5 15.5 0 1 1 0 31a15.5 15.5 0 1 1 0-31" fill="none" stroke={color} strokeWidth="3" strokeDasharray={`${pct}, 100`} />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-sm font-semibold">{pct}%</span>
    </div>
  )
}

function QuizSection({ topic, subtopic, open, onBatchComplete, onToast, onMoveFurther }) {
  const [questions, setQuestions] = useState([])
  const [idx, setIdx] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [answered, setAnswered] = useState([])
  const [feedbackVisible, setFeedbackVisible] = useState(false)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadQuiz = async () => {
    if (!topic || !subtopic) return
    setLoading(true)
    const res = await fetch(`${API}/quiz/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, subtopic }),
    })
    const data = await res.json()
    setQuestions(data.questions || [])
    setIdx(0)
    setSelectedAnswer('')
    setAnswered([])
    setFeedbackVisible(false)
    setSummary(null)
    setLoading(false)
  }

  useEffect(() => {
    if (!open) return
    loadQuiz()
  }, [topic, subtopic, open])

  if (!open) return null
  if (loading) return <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">Generating quiz...</div>

  const question = questions[idx]
  if (!question) return <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">No quiz available for this subtopic.</div>

  const isCorrect = normalize(selectedAnswer) === normalize(question.correct_answer)

  const submitCurrent = () => {
    if (!selectedAnswer) return
    const next = [...answered, {
      question: question.question,
      selected_answer: selectedAnswer,
      correct_answer: question.correct_answer,
      correct: isCorrect,
    }]
    setAnswered(next)
    setFeedbackVisible(true)
  }

  const submitBatch = async (finalAnswers) => {
    const correctCount = finalAnswers.filter((a) => a.correct).length
    const score = finalAnswers.length ? correctCount / finalAnswers.length : 0
    const res = await fetch(`${API}/quiz/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, subtopic, score, answers: finalAnswers }),
    })
    const data = await res.json()
    const finalSummary = {
      correctCount,
      total: finalAnswers.length,
      score,
      passed: score >= UNLOCK_THRESHOLD,
      server: data,
    }
    setSummary(finalSummary)
    onBatchComplete?.(finalSummary)
    onToast?.(`Batch submitted · ${Math.round(score * 100)}%`)
  }

  const nextQuestion = async () => {
    const finalAnswers = [...answered]
    if (idx >= questions.length - 1) {
      await submitBatch(finalAnswers)
      return
    }
    setIdx(idx + 1)
    setSelectedAnswer('')
    setFeedbackVisible(false)
  }

  if (summary) {
    const msg = summary.score >= 0.85 ? 'Excellent work. You are ready for the next concept.' : summary.score >= UNLOCK_THRESHOLD ? 'Solid progress. Let us continue.' : 'Let us reinforce this before moving on.'
    return (
      <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4">
        <div className="flex items-center gap-4">
          <ScoreRing score={summary.score} />
          <div>
            <p className="text-base font-semibold">You got {summary.correctCount}/{summary.total} correct — {Math.round(summary.score * 100)}%</p>
            <p className="mt-1 text-sm text-gray-300">{msg}</p>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          {summary.passed ? (
            <button onClick={onMoveFurther} className="rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-gray-950">Move Further →</button>
          ) : (
            <button onClick={loadQuiz} className="rounded-lg border border-gray-700 px-4 py-2 text-sm">Try Again</button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-teal-300">Quick Quiz</h3>
        <span className="text-xs text-gray-400">Question {idx + 1} of {questions.length}</span>
      </div>
      <div className="mb-3 flex gap-1.5">
        {questions.map((_, i) => (
          <span key={i} className={`h-2.5 w-2.5 rounded-full ${i < answered.length ? 'bg-teal-400' : 'border border-teal-400/80 bg-transparent'}`} />
        ))}
      </div>

      <p className="mb-3 text-sm text-gray-100">{question.question}</p>
      <div className="space-y-2">
        {(question.options || []).map((op, i) => {
          const showCorrect = feedbackVisible && normalize(op) === normalize(question.correct_answer)
          const showWrong = feedbackVisible && normalize(op) === normalize(selectedAnswer) && !isCorrect
          return (
            <button
              key={`${op}-${i}`}
              disabled={feedbackVisible}
              onClick={() => setSelectedAnswer(op)}
              className={`w-full rounded-xl border p-3 text-left text-sm transition-all duration-300 ${showCorrect ? 'border-green-400 bg-green-900' : showWrong ? 'border-red-400 bg-red-900' : normalize(selectedAnswer) === normalize(op) ? 'border-teal-400 bg-teal-950' : 'border-gray-700 hover:border-teal-400'} animate-[fadein_280ms_ease-out]`}
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <span className="inline-flex items-center gap-2">
                <span>{op}</span>
                {showCorrect && <Check size={14} className="text-green-300" />}
                {showWrong && <X size={14} className="text-red-300" />}
              </span>
            </button>
          )
        })}
      </div>

      {import.meta.env.DEV && (
        <div className="mt-2 text-xs text-gray-500">
          Selected: {selectedAnswer || '(none)'} | Correct: {question.correct_answer} | Match: {normalize(selectedAnswer) === normalize(question.correct_answer) ? '✓' : '✗'}
        </div>
      )}

      {feedbackVisible && <p className="mt-3 text-sm text-gray-300">{question.explanation}</p>}

      <div className="mt-3 flex gap-2">
        {!feedbackVisible ? (
          <button onClick={submitCurrent} disabled={!selectedAnswer} className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950 disabled:opacity-50">Submit Answer</button>
        ) : (
          <button onClick={nextQuestion} className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950">Next Question →</button>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [topics, setTopics] = useState([])
  const [studentState, setStudentState] = useState(null)
  const [selectedTopic, setSelectedTopic] = useState('')
  const [currentSubtopic, setCurrentSubtopic] = useState('')
  const [messages, setMessages] = useState([])
  const [quizOpen, setQuizOpen] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [waitingFirstChunk, setWaitingFirstChunk] = useState(false)
  const [toast, setToast] = useState('')
  const [topicComplete, setTopicComplete] = useState(false)

  const activeMessageId = useRef(null)
  const bottomRef = useRef(null)
  const toastTimer = useRef(null)

  const refreshData = () => Promise.all([
    fetch(`${API}/student/state`).then((r) => r.json()),
    fetch(`${API}/student/topics`).then((r) => r.json()),
  ]).then(([state, t]) => {
    setStudentState(state)
    setTopics(t.topics || [])
    if (!selectedTopic && (t.topics || [])[0]?.name) {
      const topic = t.topics[0].name
      setSelectedTopic(topic)
      setCurrentSubtopic(TOPIC_SUBTOPICS[topic]?.[0]?.id || '')
    }
  })

  useEffect(() => { refreshData() }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, quizOpen, waitingFirstChunk, topicComplete])

  const showToast = (msg) => {
    setToast(msg)
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 3000)
  }

  const streamTopic = (topic, subtopic) => {
    const tutorId = `t-${Date.now()}`
    activeMessageId.current = tutorId
    setMessages((m) => [...m, { id: tutorId, role: 'tutor', text: '', meta: {} }])
    setQuizOpen(false)
    setStreaming(true)
    setWaitingFirstChunk(true)

    const es = new EventSource(`${API}/tutor/explain/stream?topic=${encodeURIComponent(topic)}&subtopic=${encodeURIComponent(subtopic || '')}`)
    es.onmessage = (event) => {
      const data = JSON.parse(event.data || '{}')
      const delta = data.delta || ''
      if (delta) {
        setWaitingFirstChunk(false)
        setMessages((msgs) => msgs.map((m) => (m.id === tutorId ? { ...m, text: `${m.text || ''}${delta}` } : m)))
      }
      if (data.done) {
        setStreaming(false)
        setWaitingFirstChunk(false)
        setQuizOpen(true)
        es.close()
        refreshData()
      }
    }
    es.onerror = () => {
      setStreaming(false)
      setWaitingFirstChunk(false)
      es.close()
    }
  }

  const startStream = () => {
    if (!selectedTopic || streaming) return
    const subtopic = currentSubtopic || TOPIC_SUBTOPICS[selectedTopic]?.[0]?.id || ''
    setCurrentSubtopic(subtopic)
    setTopicComplete(false)
    setMessages((m) => [...m, { id: `s-${Date.now()}`, role: 'student', text: `Teach me ${selectedTopic} (${subtopic}).` }])
    streamTopic(selectedTopic, subtopic)
  }

  const handleMoveFurther = async () => {
    const res = await fetch(`${API}/curriculum/next`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_topic: selectedTopic, current_subtopic: currentSubtopic }),
    })
    const data = await res.json()
    if (data.topic_complete) {
      setTopicComplete(true)
      setQuizOpen(false)
      return
    }
    const nextSub = data.next_subtopic
    setCurrentSubtopic(nextSub)
    setMessages((m) => [...m, { id: `s-${Date.now()}`, role: 'student', text: `Move further to ${nextSub}.` }])
    streamTopic(selectedTopic, nextSub)
  }

  const heatmap = useMemo(() => {
    const concepts = studentState?.knowledge_state?.concepts || {}
    return Object.entries(concepts).map(([name, data]) => ({
      name,
      mastery: Number(data?.mastery || 0),
      attempts: Number(data?.attempts || 0),
    }))
  }, [studentState])

  const score = Number(studentState?.last_score || 0)
  const cycles = (studentState?.accuracy_history || []).length
  const status = (studentState?.macro_decision?.action || 'active').replaceAll('_', ' ')
  const progressPct = Math.max(0, Math.min(100, (score / 0.85) * 100))

  return (
    <div className="h-screen overflow-hidden bg-gray-950 font-[Inter,system-ui] text-gray-100">
      <div className="w-full border-b border-gray-800 bg-gray-900 p-3">
        <div className="mb-2 text-xs text-gray-300">Session Progress · {cycles} cycles · {status}</div>
        <div className="h-2 overflow-hidden rounded-full bg-gray-800">
          <div className="h-full bg-gradient-to-r from-teal-500 to-green-500 transition-all duration-500" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {toast && <div className="fixed right-4 top-4 z-50 rounded-lg border border-teal-500 bg-gray-900 px-4 py-2 text-sm text-teal-300 shadow-lg">{toast}</div>}

      <div className="flex h-[calc(100vh-66px)]">
        <aside className="w-[280px] shrink-0 border-r border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-xs uppercase tracking-wider text-teal-300">Topics</h2>
          <div className="space-y-2 overflow-y-auto max-h-[34vh] pr-1">
            {topics.map((t) => (
              <button
                key={t.name}
                onClick={() => {
                  setSelectedTopic(t.name)
                  setCurrentSubtopic(TOPIC_SUBTOPICS[t.name]?.[0]?.id || '')
                  setTopicComplete(false)
                }}
                className={`w-full rounded-xl border p-3 text-left transition ${selectedTopic === t.name ? 'border-teal-500 bg-teal-950' : 'border-gray-800 bg-gray-900 hover:border-teal-500'}`}
              >
                <div className="text-sm capitalize">{t.name}</div>
                <div className="mt-2 text-xs text-gray-400">Attempts {t.attempts || 0}</div>
              </button>
            ))}
          </div>

          <h3 className="mb-2 mt-5 text-xs uppercase tracking-wider text-teal-300">Mastery Heatmap</h3>
          <div className="space-y-2">
            {heatmap.map((c) => (
              <div key={c.name} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 px-2 py-2">
                <span className="text-xs capitalize text-gray-300">{c.name}</span>
                <span className={`rounded-full px-2 py-1 text-[10px] text-white transition-colors duration-500 ${masteryPillClass(c.mastery)}`}>{Math.round(c.mastery * 100)}%</span>
              </div>
            ))}
          </div>
        </aside>

        <main className="flex-1 bg-[#0d1117] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-sm text-gray-300">Tutor Chat · {currentSubtopic || 'subtopic not set'}</h1>
            <button onClick={startStream} disabled={!selectedTopic || streaming} className="rounded-lg bg-teal-500 px-4 py-2 text-xs font-semibold text-gray-950 disabled:opacity-50">
              {streaming ? 'Streaming...' : `Explain ${selectedTopic || ''}`}
            </button>
          </div>

          <div className="h-full overflow-y-auto max-h-[60vh] scroll-smooth pr-1">
            <div className="space-y-4">
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.role === 'student' ? 'justify-end' : 'justify-start'}`}>
                  {m.role === 'student' ? (
                    <div className="max-w-[75%] rounded-2xl border border-gray-700 bg-gray-800 px-4 py-3 text-sm">{m.text}</div>
                  ) : (
                    <div className="max-w-[85%]">
                      <div className="mb-1 flex items-center gap-2 text-xs text-teal-300">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-teal-500/20 shadow-[0_0_16px_rgba(20,184,166,0.4)]"><Bot size={14} /></span>
                        <span>Tutor</span>
                      </div>
                      <div className="rounded-2xl border border-gray-700 bg-slate-800 p-4">
                        {waitingFirstChunk && m.id === activeMessageId.current && !m.text ? <ThinkingState /> : <TutorMarkdown text={m.text} streaming={streaming && m.id === activeMessageId.current} />}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              <QuizSection
                topic={selectedTopic}
                subtopic={currentSubtopic}
                open={quizOpen}
                onBatchComplete={() => refreshData()}
                onToast={showToast}
                onMoveFurther={handleMoveFurther}
              />

              {topicComplete && (
                <div className="rounded-2xl border border-green-500/40 bg-green-950/40 p-4">
                  <p className="text-base font-semibold text-green-300">Topic Complete</p>
                  <p className="mt-1 text-sm text-gray-300">You finished all configured subtopics for {selectedTopic}. Next topic is now unlocked in your learning path.</p>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
