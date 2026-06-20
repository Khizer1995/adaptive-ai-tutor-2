import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Bot, Check, X, ChevronDown, ChevronRight, AlertTriangle, TrendingUp, BookOpen, Zap, LogOut, User } from 'lucide-react'
import StudyQuestionnaire from './StudyQuestionnaire'
import { useAuth } from './context/AuthContext'

const API = 'http://localhost:8000'
const UNLOCK_THRESHOLD = 0.7

// ── Adaptive mode badge colours ─────────────────────────────────────────────
const ADAPTIVE_MODE_STYLES = {
  remedial: {
    label: 'Remedial Mode — Simplified',
    icon: AlertTriangle,
    cls: 'border-orange-500/50 bg-orange-950/30 text-orange-300',
  },
  guided: {
    label: 'Guided Mode — Standard',
    icon: BookOpen,
    cls: 'border-teal-500/40 bg-teal-950/20 text-teal-300',
  },
  advanced: {
    label: 'Advanced Mode — Deep Dive',
    icon: Zap,
    cls: 'border-purple-500/50 bg-purple-950/30 text-purple-300',
  },
}

const normalize = (s = '') => s.trim().toLowerCase().replace(/\s+/g, ' ')

function masteryPillClass(mastery) {
  if (mastery < 0.4) return 'bg-red-800'
  if (mastery <= 0.7) return 'bg-yellow-700'
  return 'bg-green-700'
}

// ── Shared components ────────────────────────────────────────────────────────

function ThinkingState() {
  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
      <div className="mb-2 flex gap-2 text-teal-400">
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" style={{ animationDelay: '0.12s' }} />
        <span className="h-2 w-2 animate-bounce rounded-full bg-teal-400" style={{ animationDelay: '0.24s' }} />
      </div>
      <p className="text-sm text-gray-300">Analysing your learning state and adapting content…</p>
    </div>
  )
}

function AdaptiveBadge({ mode }) {
  const cfg = ADAPTIVE_MODE_STYLES[mode] || ADAPTIVE_MODE_STYLES.guided
  const Icon = cfg.icon
  return (
    <div className={`mb-3 flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${cfg.cls}`}>
      <Icon size={12} />
      <span>{cfg.label}</span>
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

// ── Quiz Section — only rendered on demand, NOT below content ─────────────
// Issue #4 fix: quizOpen starts as false and is set true ONLY when the user
// clicks "Start Learning Assessment", not automatically after content loads.

function QuizSection({ topic, subtopic, open, onBatchComplete, onToast, onMoveFurther }) {
  const { accessToken } = useAuth()
  const [questions, setQuestions] = useState([])
  const [idx, setIdx] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [answered, setAnswered] = useState([])
  const [feedbackVisible, setFeedbackVisible] = useState(false)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [adaptiveMessage, setAdaptiveMessage] = useState('')

  const loadQuiz = async () => {
    if (!topic || !subtopic) return
    setLoading(true)
    setSummary(null)
    setAnswered([])
    setIdx(0)
    setSelectedAnswer('')
    setFeedbackVisible(false)
    setAdaptiveMessage('')
    const res = await fetch(`${API}/quiz/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ topic, subtopic }),
    })
    const data = await res.json()
    setQuestions(data.questions || [])
    setLoading(false)
  }

  // Issue #4: only load quiz when the section is explicitly opened (not auto).
  useEffect(() => {
    if (!open) return
    loadQuiz()
  }, [topic, subtopic, open]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null
  if (loading) return (
    <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
      Generating adaptive quiz…
    </div>
  )

  const question = questions[idx]
  if (!question && !summary) return (
    <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
      No quiz available for this subtopic.
    </div>
  )

  const isCorrect = question && normalize(selectedAnswer) === normalize(question.correct_answer)

  const submitCurrent = () => {
    if (!selectedAnswer || !question) return
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
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
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
    // Issue #1: show adaptive feedback message from backend.
    if (data.adaptive_message) setAdaptiveMessage(data.adaptive_message)
    onBatchComplete?.(finalSummary)
    onToast?.(`Quiz submitted · ${Math.round(score * 100)}%`)
  }

  const nextQuestion = async () => {
    if (idx >= questions.length - 1) {
      await submitBatch([...answered])
      return
    }
    setIdx(idx + 1)
    setSelectedAnswer('')
    setFeedbackVisible(false)
  }

  if (summary) {
    const msg = summary.score >= 0.85
      ? 'Excellent! You are ready for the next concept.'
      : summary.score >= UNLOCK_THRESHOLD
        ? 'Solid progress. Let us continue.'
        : 'Let us reinforce this before moving on.'
    return (
      <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4">
        <div className="flex items-center gap-4">
          <ScoreRing score={summary.score} />
          <div>
            <p className="text-base font-semibold">
              {summary.correctCount}/{summary.total} correct — {Math.round(summary.score * 100)}%
            </p>
            <p className="mt-1 text-sm text-gray-300">{msg}</p>
          </div>
        </div>
        {/* Issue #1: adaptive message shown after quiz */}
        {adaptiveMessage && (
          <div className="mt-3 rounded-lg border border-teal-500/30 bg-teal-950/20 px-3 py-2 text-xs text-teal-300">
            <TrendingUp size={12} className="mr-1 inline" />
            {adaptiveMessage}
          </div>
        )}
        <div className="mt-4 flex gap-2">
          {summary.passed ? (
            <button
              id="quiz-move-further-btn"
              onClick={onMoveFurther}
              className="rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-gray-950"
            >
              Move Further →
            </button>
          ) : (
            <button
              id="quiz-retry-btn"
              onClick={loadQuiz}
              className="rounded-lg border border-gray-700 px-4 py-2 text-sm"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-teal-300">Learning Assessment</h3>
        <span className="text-xs text-gray-400">Question {idx + 1} of {questions.length}</span>
      </div>
      <div className="mb-3 flex gap-1.5">
        {questions.map((_, i) => (
          <span
            key={i}
            className={`h-2.5 w-2.5 rounded-full ${i < answered.length ? 'bg-teal-400' : 'border border-teal-400/80 bg-transparent'}`}
          />
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
              id={`quiz-option-${i}`}
              disabled={feedbackVisible}
              onClick={() => setSelectedAnswer(op)}
              className={`w-full rounded-xl border p-3 text-left text-sm transition-all duration-300 ${
                showCorrect ? 'border-green-400 bg-green-900' :
                showWrong ? 'border-red-400 bg-red-900' :
                normalize(selectedAnswer) === normalize(op) ? 'border-teal-400 bg-teal-950' :
                'border-gray-700 hover:border-teal-400'
              } animate-[fadein_280ms_ease-out]`}
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
          Selected: {selectedAnswer || '(none)'} | Correct: {question.correct_answer} |
          Match: {normalize(selectedAnswer) === normalize(question.correct_answer) ? '✓' : '✗'}
        </div>
      )}

      {feedbackVisible && (
        <p className="mt-3 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300">
          {question.explanation}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        {!feedbackVisible ? (
          <button
            id="quiz-submit-btn"
            onClick={submitCurrent}
            disabled={!selectedAnswer}
            className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950 disabled:opacity-50"
          >
            Submit Answer
          </button>
        ) : (
          <button
            id="quiz-next-btn"
            onClick={nextQuestion}
            className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950"
          >
            Next Question →
          </button>
        )}
      </div>
    </div>
  )
}

// ── Assessment section (pretest / posttest) ──────────────────────────────────

function AssessmentSection({ topic, subtopic, mode, open, onComplete, onToast }) {
  const { accessToken } = useAuth()
  const [questions, setQuestions] = useState([])
  const [idx, setIdx] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [answered, setAnswered] = useState([])
  const [feedbackVisible, setFeedbackVisible] = useState(false)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)

  const endpoint = mode === 'posttest' ? '/quiz/posttest' : '/quiz/pretest'
  const title = mode === 'posttest' ? 'Complete Assessment' : 'Start Learning Assessment'

  const loadAssessment = async () => {
    if (!topic) return
    setLoading(true)
    const res = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
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
    loadAssessment()
  }, [topic, subtopic, mode, open]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null
  if (loading) return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
      Preparing assessment…
    </div>
  )

  const question = questions[idx]
  if (!question && !summary) return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
      No assessment available.
    </div>
  )

  const isCorrect = question && normalize(selectedAnswer) === normalize(question.correct_answer)

  const submitCurrent = () => {
    if (!selectedAnswer || !question) return
    setAnswered([...answered, {
      question: question.question,
      selected_answer: selectedAnswer,
      correct_answer: question.correct_answer,
      correct: isCorrect,
    }])
    setFeedbackVisible(true)
  }

  const submitAssessment = async (finalAnswers) => {
    const res = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ topic, subtopic, answers: finalAnswers }),
    })
    const data = await res.json()
    setSummary(data)
    onComplete?.(data)
    onToast?.(`${title} submitted · ${Math.round((data.score || 0) * 100)}%`)
  }

  const nextQuestion = async () => {
    if (idx >= questions.length - 1) {
      await submitAssessment([...answered])
      return
    }
    setIdx(idx + 1)
    setSelectedAnswer('')
    setFeedbackVisible(false)
  }

  if (summary) {
    return (
      <div className="rounded-2xl border border-teal-500/40 bg-teal-950/30 p-4">
        <div className="flex items-center gap-4">
          <ScoreRing score={Number(summary.score || 0)} />
          <div>
            <p className="text-base font-semibold">
              {title} Score: {Math.round((summary.score || 0) * 100)}%
            </p>
            {mode === 'posttest' && (
              <p className="mt-1 text-sm text-gray-300">
                Pre {Math.round((summary.pretest_score || 0) * 100)}% · Post{' '}
                {Math.round((summary.posttest_score || 0) * 100)}% · Gain{' '}
                {Math.round((summary.learning_gain || 0) * 100)}%
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-teal-500/40 bg-gray-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-teal-300">{title}</h3>
        <span className="text-xs text-gray-400">Question {idx + 1} of {questions.length}</span>
      </div>
      <p className="mb-3 text-sm text-gray-100">{question.question}</p>
      <div className="space-y-2">
        {(question.options || []).map((op, i) => {
          const showCorrect = feedbackVisible && normalize(op) === normalize(question.correct_answer)
          const showWrong = feedbackVisible && normalize(op) === normalize(selectedAnswer) && !isCorrect
          return (
            <button
              key={`${op}-${i}`}
              id={`assessment-option-${i}`}
              disabled={feedbackVisible}
              onClick={() => setSelectedAnswer(op)}
              className={`w-full rounded-xl border p-3 text-left text-sm transition ${
                showCorrect ? 'border-green-400 bg-green-900' :
                showWrong ? 'border-red-400 bg-red-900' :
                normalize(selectedAnswer) === normalize(op) ? 'border-teal-400 bg-teal-950' :
                'border-gray-700 hover:border-teal-400'
              }`}
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
      {feedbackVisible && (
        <p className="mt-3 text-sm text-gray-300">{question.explanation}</p>
      )}
      <div className="mt-3">
        {!feedbackVisible ? (
          <button
            id="assessment-submit-btn"
            onClick={submitCurrent}
            disabled={!selectedAnswer}
            className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950 disabled:opacity-50"
          >
            Submit Answer
          </button>
        ) : (
          <button
            id="assessment-next-btn"
            onClick={nextQuestion}
            className="rounded-lg bg-teal-500 px-3 py-2 text-xs font-semibold text-gray-950"
          >
            Next Question &gt;
          </button>
        )}
      </div>
    </div>
  )
}

// ── Topic Sidebar — now shows ALL topics with collapsible subtopics ──────────
// Issue #5 fix: topics come from /student/topics which now returns all 7 DSA
// topics with their subtopic lists and per-student progress enrichment.

function TopicSidebar({ topics, selectedTopic, currentSubtopic, onSelectSubtopic }) {
  const [expandedTopics, setExpandedTopics] = useState({})

  // Auto-expand the selected topic.
  useEffect(() => {
    if (selectedTopic) {
      setExpandedTopics((prev) => ({ ...prev, [selectedTopic]: true }))
    }
  }, [selectedTopic])

  const toggleTopic = (name) => {
    setExpandedTopics((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div className="space-y-1">
      {topics.map((t) => {
        const isSelected = selectedTopic === t.name
        const isExpanded = expandedTopics[t.name]
        const mastery = Number(t.mastery || 0)

        return (
          <div key={t.name}>
            {/* Topic row */}
            <button
              id={`topic-btn-${t.name}`}
              onClick={() => toggleTopic(t.name)}
              className={`flex w-full items-center justify-between rounded-xl border p-3 text-left transition ${
                isSelected
                  ? 'border-teal-500 bg-teal-950'
                  : 'border-gray-800 bg-gray-900 hover:border-teal-500'
              }`}
            >
              <div>
                <div className="text-sm capitalize">{t.name.replace(/_/g, ' ')}</div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-700">
                    <div
                      className="h-full bg-teal-500 transition-all duration-500"
                      style={{ width: `${Math.round(mastery * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-gray-400">{Math.round(mastery * 100)}%</span>
                  {t.completed && (
                    <span className="rounded-full bg-green-800 px-1.5 py-0.5 text-[10px] text-green-200">
                      ✓
                    </span>
                  )}
                </div>
              </div>
              {isExpanded ? (
                <ChevronDown size={14} className="shrink-0 text-gray-400" />
              ) : (
                <ChevronRight size={14} className="shrink-0 text-gray-400" />
              )}
            </button>

            {/* Subtopic list */}
            {isExpanded && (t.subtopics || []).length > 0 && (
              <div className="ml-3 mt-1 space-y-0.5 border-l border-gray-700 pl-3">
                {t.subtopics.map((sub) => {
                  const isActiveSub = currentSubtopic === sub.id
                  return (
                    <button
                      key={sub.id}
                      id={`subtopic-btn-${sub.id}`}
                      onClick={() => onSelectSubtopic(t.name, sub.id)}
                      className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs transition ${
                        isActiveSub
                          ? 'bg-teal-900 text-teal-200'
                          : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                      }`}
                    >
                      <span className="truncate">{sub.title}</span>
                      {sub.passed && <Check size={10} className="ml-1 shrink-0 text-green-400" />}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const { accessToken, userName, logout, studentId } = useAuth()

  // Build auth headers for all fetch() calls
  const authHeaders = useCallback(
    () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` }),
    [accessToken]
  )

  const [topics, setTopics] = useState([])
  const [studentState, setStudentState] = useState(null)
  const [selectedTopic, setSelectedTopic] = useState('')
  const [currentSubtopic, setCurrentSubtopic] = useState('')
  const [messages, setMessages] = useState([])
  const [quizOpen, setQuizOpen] = useState(false)   // Issue #4: starts false
  const [streaming, setStreaming] = useState(false)
  const [waitingFirstChunk, setWaitingFirstChunk] = useState(false)
  const [toast, setToast] = useState('')
  const [topicComplete, setTopicComplete] = useState(false)
  const [assessmentOpen, setAssessmentOpen] = useState(false)
  const [assessmentMode, setAssessmentMode] = useState('pretest')
  const [currentAdaptiveMode, setCurrentAdaptiveMode] = useState('guided')
  const [contentReady, setContentReady] = useState(false) // track if content has loaded

  const activeMessageId = useRef(null)
  const bottomRef = useRef(null)
  const toastTimer = useRef(null)

  const refreshData = useCallback(() =>
    Promise.all([
      fetch(`${API}/student/state`,  { headers: authHeaders() }).then((r) => r.json()),
      fetch(`${API}/student/topics`, { headers: authHeaders() }).then((r) => r.json()),
    ]).then(([state, t]) => {
      setStudentState(state)
      const allTopics = t.topics || []
      setTopics(allTopics)
      if (!selectedTopic && allTopics[0]?.name) {
        const topic = allTopics[0].name
        setSelectedTopic(topic)
        const firstSub = allTopics[0].subtopics?.[0]?.id || ''
        setCurrentSubtopic(firstSub)
      }
    }),
  [selectedTopic, authHeaders]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { refreshData() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, quizOpen, waitingFirstChunk, topicComplete])

  const showToast = (msg) => {
    setToast(msg)
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 3500)
  }

  const streamTopic = (topic, subtopic) => {
    const tutorId = `t-${Date.now()}`
    activeMessageId.current = tutorId
    setMessages((m) => [...m, { id: tutorId, role: 'tutor', text: '', meta: {}, adaptiveMode: 'guided' }])
    // Issue #4: close quiz and mark content as not ready yet
    setQuizOpen(false)
    setContentReady(false)
    setStreaming(true)
    setWaitingFirstChunk(true)

    // Pass token as ?token= query param — EventSource can't send custom headers
    const url = `${API}/tutor/explain/stream?topic=${encodeURIComponent(topic)}&subtopic=${encodeURIComponent(subtopic || '')}&token=${encodeURIComponent(accessToken || '')}`
    const es = new EventSource(url)
    es.onmessage = (event) => {
      const data = JSON.parse(event.data || '{}')
      const delta = data.delta || ''
      if (delta) {
        setWaitingFirstChunk(false)
        setMessages((msgs) =>
          msgs.map((m) =>
            m.id === tutorId
              ? { ...m, text: `${m.text || ''}${delta}`, adaptiveMode: data.meta?.adaptive_mode || m.adaptiveMode }
              : m
          )
        )
      }
      if (data.meta?.adaptive_mode) {
        setCurrentAdaptiveMode(data.meta.adaptive_mode)
      }
      if (data.done) {
        setStreaming(false)
        setWaitingFirstChunk(false)
        // Issue #4: content is ready — user can now CHOOSE to start the quiz.
        setContentReady(true)
        // Do NOT auto-open quiz.
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
    const subtopic = currentSubtopic || ''
    setTopicComplete(false)
    setMessages((m) => [...m, {
      id: `s-${Date.now()}`,
      role: 'student',
      text: `Teach me: ${selectedTopic.replace(/_/g, ' ')}${subtopic ? ` — ${subtopic}` : ''}.`,
    }])
    streamTopic(selectedTopic, subtopic)
  }

  // Issue #4: quiz is opened ONLY by explicit user click.
  const openQuiz = () => {
    if (!selectedTopic || streaming) return
    setAssessmentOpen(false)
    setQuizOpen(true)
  }

  const openAssessment = (mode) => {
    if (!selectedTopic) return
    const subtopic = currentSubtopic || `${selectedTopic}_assessment`
    setCurrentSubtopic(subtopic)
    setAssessmentMode(mode)
    setAssessmentOpen(true)
    setQuizOpen(false)
  }

  const handleSelectSubtopic = (topicName, subtopicId) => {
    setSelectedTopic(topicName)
    setCurrentSubtopic(subtopicId)
    setTopicComplete(false)
    setQuizOpen(false)
    setContentReady(false)
  }

  const handleMoveFurther = async () => {
    const payload = { current_topic: selectedTopic, current_subtopic: currentSubtopic }
    const res = await fetch(`${API}/curriculum/next`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    if (data.topic_complete) {
      setTopicComplete(true)
      setQuizOpen(false)
      return
    }
    const nextSub = data.next_subtopic
    setCurrentSubtopic(nextSub)
    setQuizOpen(false)
    setContentReady(false)
    setMessages((m) => [...m, { id: `s-${Date.now()}`, role: 'student', text: `Moving to: ${nextSub}.` }])
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
  const hasPretest = studentState?.pretest_score !== null && studentState?.pretest_score !== undefined

  return (
    <div className="h-screen overflow-hidden bg-gray-950 font-[Inter,system-ui] text-gray-100">
      {/* Top bar */}
      <div className="w-full border-b border-gray-800 bg-gray-900 px-3 py-2">
        <div className="flex items-center justify-between">
          {/* Left: progress info */}
          <div className="text-xs text-gray-300">
            Session Progress · {cycles} cycles · {status}
            {studentState?.level && (
              <span className="ml-2 rounded-full border border-teal-500/50 px-2 py-0.5 text-teal-300">
                {studentState.level}
              </span>
            )}
          </div>
          {/* Right: user badge + logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-800 px-3 py-1">
              <User size={12} className="text-teal-400" />
              <span className="text-xs text-gray-300 max-w-[140px] truncate">{userName}</span>
            </div>
            <button
              id="logout-btn"
              onClick={logout}
              className="flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-400 transition-colors hover:border-red-500/50 hover:bg-red-950/30 hover:text-red-400"
              title="Sign out"
            >
              <LogOut size={12} />
              Sign out
            </button>
          </div>
        </div>
        {/* Progress bar */}
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-800">
          <div
            className="h-full bg-gradient-to-r from-teal-500 to-green-500 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {toast && (
        <div className="fixed right-4 top-4 z-50 rounded-lg border border-teal-500 bg-gray-900 px-4 py-2 text-sm text-teal-300 shadow-lg">
          {toast}
        </div>
      )}

      <div className="flex h-[calc(100vh-66px)]">
        {/* Sidebar — Issue #5 fix: full topic tree */}
        <aside className="w-[300px] shrink-0 overflow-y-auto border-r border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-xs uppercase tracking-wider text-teal-300">Topics</h2>
          <TopicSidebar
            topics={topics}
            selectedTopic={selectedTopic}
            currentSubtopic={currentSubtopic}
            onSelectSubtopic={handleSelectSubtopic}
          />

          {heatmap.length > 0 && (
            <>
              <h3 className="mb-2 mt-6 text-xs uppercase tracking-wider text-teal-300">Mastery Heatmap</h3>
              <div className="space-y-2">
                {heatmap.map((c) => (
                  <div key={c.name} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 px-2 py-2">
                    <span className="text-xs capitalize text-gray-300">{c.name.replace(/_/g, ' ')}</span>
                    <span className={`rounded-full px-2 py-1 text-[10px] text-white transition-colors duration-500 ${masteryPillClass(c.mastery)}`}>
                      {Math.round(c.mastery * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </aside>

        {/* Main chat area */}
        <main className="flex-1 bg-[#0d1117] p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h1 className="text-sm text-gray-300">
                {selectedTopic
                  ? `${selectedTopic.replace(/_/g, ' ')}${currentSubtopic ? ` › ${currentSubtopic}` : ''}`
                  : 'Select a topic to begin'}
              </h1>
            </div>
            <div className="flex gap-2">
              {/* Issue #4: "Start Learning Assessment" opens quiz ONLY — separate from content */}
              {contentReady && !quizOpen && (
                <button
                  id="start-quiz-btn"
                  onClick={openQuiz}
                  disabled={!selectedTopic || streaming}
                  className="rounded-lg border border-teal-500 px-4 py-2 text-xs font-semibold text-teal-300 disabled:opacity-50 hover:bg-teal-950 transition"
                >
                  Start Learning Assessment
                </button>
              )}
              {!hasPretest && (
                <button
                  id="pretest-btn"
                  onClick={() => openAssessment('pretest')}
                  disabled={!selectedTopic || streaming}
                  className="rounded-lg border border-purple-500/60 px-4 py-2 text-xs font-semibold text-purple-300 disabled:opacity-50"
                >
                  Pre-Test
                </button>
              )}
              <button
                id="explain-btn"
                onClick={startStream}
                disabled={!selectedTopic || streaming}
                className="rounded-lg bg-teal-500 px-4 py-2 text-xs font-semibold text-gray-950 disabled:opacity-50"
              >
                {streaming ? 'Generating…' : `Explain ${selectedTopic ? selectedTopic.replace(/_/g, ' ') : ''}`}
              </button>
            </div>
          </div>

          <div className="h-full max-h-[calc(100vh-140px)] overflow-y-auto scroll-smooth pr-1">
            <div className="space-y-4">
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.role === 'student' ? 'justify-end' : 'justify-start'}`}>
                  {m.role === 'student' ? (
                    <div className="max-w-[75%] rounded-2xl border border-gray-700 bg-gray-800 px-4 py-3 text-sm">
                      {m.text}
                    </div>
                  ) : (
                    <div className="max-w-[85%]">
                      <div className="mb-1 flex items-center gap-2 text-xs text-teal-300">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-teal-500/20 shadow-[0_0_16px_rgba(20,184,166,0.4)]">
                          <Bot size={14} />
                        </span>
                        <span>Tutor</span>
                      </div>
                      <div className="rounded-2xl border border-gray-700 bg-slate-800 p-4">
                        {/* Issue #1: show adaptive mode badge */}
                        {m.adaptiveMode && !waitingFirstChunk && m.text && (
                          <AdaptiveBadge mode={m.adaptiveMode} />
                        )}
                        {waitingFirstChunk && m.id === activeMessageId.current && !m.text ? (
                          <ThinkingState />
                        ) : (
                          <TutorMarkdown
                            text={m.text}
                            streaming={streaming && m.id === activeMessageId.current}
                          />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Assessment (pretest / posttest) — separate from quiz */}
              <AssessmentSection
                topic={selectedTopic}
                subtopic={currentSubtopic}
                mode={assessmentMode}
                open={assessmentOpen}
                onComplete={() => {
                  refreshData()
                  if (assessmentMode === 'pretest') setAssessmentOpen(false)
                }}
                onToast={showToast}
              />

              {/* Issue #4: QuizSection only renders when quizOpen=true (user clicked button) */}
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
                  <p className="text-base font-semibold text-green-300">Topic Complete 🎉</p>
                  <p className="mt-1 text-sm text-gray-300">
                    You have finished all subtopics for {selectedTopic?.replace(/_/g, ' ')}.
                    The next topic is now unlocked.
                  </p>
                  <button
                    id="posttest-btn"
                    onClick={() => openAssessment('posttest')}
                    className="mt-4 rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-gray-950"
                  >
                    Take Complete Assessment
                  </button>
                </div>
              )}

              {studentState?.posttest_score !== null && studentState?.posttest_score !== undefined && (
                <>
                  <div className="rounded-2xl border border-teal-500/40 bg-gray-900 p-4 text-sm text-gray-300">
                    Pre-test {Math.round((studentState.pretest_score || 0) * 100)}% · Post-test{' '}
                    {Math.round((studentState.posttest_score || 0) * 100)}% · Learning gain{' '}
                    {Math.round((studentState.learning_gain || 0) * 100)}%
                  </div>
                  <StudyQuestionnaire
                    apiBase={API}
                    topic={selectedTopic}
                    subtopic={currentSubtopic}
                    studentId={studentState.student_id}
                    onToast={showToast}
                  />
                </>
              )}

              <div ref={bottomRef} />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
