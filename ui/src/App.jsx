import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Bot, Check, X, ChevronDown, ChevronRight, AlertTriangle, TrendingUp, BookOpen, Zap, LogOut, User } from 'lucide-react'
import StudyQuestionnaire from './StudyQuestionnaire'
import { useAuth } from './context/AuthContext'

const API = import.meta.env.VITE_API_BASE_URL || 'https://cognitive-adaptive-ai-tutor-production.up.railway.app'
const UNLOCK_THRESHOLD = 0.7

// ── Adaptive mode badge colours ─────────────────────────────────────────────
const ADAPTIVE_MODE_STYLES = {
  remedial: {
    label: 'Remedial Mode — Simplified',
    icon: AlertTriangle,
    cls: 'border-amber-500/50 bg-amber-950/30 text-amber-300',
  },
  guided: {
    label: 'Guided Mode — Standard',
    icon: BookOpen,
    cls: 'border-indigo-500/40 bg-indigo-950/20 text-indigo-300',
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
  if (mastery <= 0.7) return 'bg-amber-700'
  return 'bg-emerald-700'
}

// ── Shared components ────────────────────────────────────────────────────────

function ThinkingState() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <div className="mb-2 flex gap-2 text-indigo-400">
        <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: '0.12s' }} />
        <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: '0.24s' }} />
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
      {streaming && <span className="ml-1 inline-block h-4 w-[2px] animate-pulse bg-indigo-400 align-middle" />}
    </div>
  )
}

function ScoreRing({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? '#6366f1' : pct >= 50 ? '#f59e0b' : '#ef4444'
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
  // selectedIndex: integer 0-3 for MCQ, or option text string for LLM questions
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [answered, setAnswered] = useState([])
  const [feedbackVisible, setFeedbackVisible] = useState(false)
  // serverFeedback: {correct: bool, explanation: str} returned by /quiz/mcq/submit
  const [serverFeedback, setServerFeedback] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [adaptiveMessage, setAdaptiveMessage] = useState('')

  const loadQuiz = async () => {
    if (!topic) return  // Only require topic, subtopic is optional (practice is topic-level)
    setLoading(true)
    setSummary(null)
    setAnswered([])
    setIdx(0)
    setSelectedIndex(null)
    setFeedbackVisible(false)
    setServerFeedback(null)
    setAdaptiveMessage('')
    const res = await fetch(`${API}/quiz/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ topic, subtopic: subtopic || topic }),  // Use topic as fallback
    })
    const data = await res.json()
    console.log('Practice quiz response:', data)  // Debug logging
    setQuestions(data.questions || [])
    setLoading(false)
  }

  useEffect(() => {
    if (!open) return
    loadQuiz()
  }, [topic, subtopic, open]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null
  if (loading) return (
    <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
      Generating adaptive quiz…
    </div>
  )

  const question = questions[idx]
  if (!question && !summary) return (
    <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
      No quiz available for this subtopic.
    </div>
  )

  // Detect MCQ bank question (has .id from bank, question_type='mcq', no correct_answer)
  const isMCQ = question && question.question_type === 'mcq' && !question.correct_answer

  // ── Submit one answer ───────────────────────────────────────────────────────
  const submitCurrent = async () => {
    if (!question) return
    if (isMCQ) {
      if (selectedIndex === null) return
      setSubmitting(true)
      try {
        const res = await fetch(`${API}/quiz/mcq/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
          body: JSON.stringify({ question_id: question.id, chosen_index: selectedIndex, context: 'practice' }),
        })
        const data = await res.json()
        setServerFeedback(data)
        setAnswered(prev => [...prev, { question_id: question.id, chosen_index: selectedIndex, correct: data.correct }])
        setFeedbackVisible(true)
      } finally {
        setSubmitting(false)
      }
    } else {
      // Legacy LLM path: local text comparison
      if (!selectedIndex && selectedIndex !== 0) return
      const selectedText = typeof selectedIndex === 'string' ? selectedIndex : (question.options || [])[selectedIndex] || ''
      const isCorrect = normalize(selectedText) === normalize(question.correct_answer)
      setAnswered(prev => [...prev, {
        question: question.question,
        selected_answer: selectedText,
        correct_answer: question.correct_answer,
        correct: isCorrect,
      }])
      setFeedbackVisible(true)
    }
  }

  // ── After last question: submit batch for mastery update ────────────────────
  const submitBatch = async (finalAnswers) => {
    const correctCount = finalAnswers.filter(a => a.correct).length
    const score = finalAnswers.length ? correctCount / finalAnswers.length : 0

    if (isMCQ || (questions[0] && questions[0].question_type === 'mcq')) {
      // MCQ path: send pre-computed score to existing /quiz/submit endpoint
      const res = await fetch(`${API}/quiz/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ topic, subtopic, score, answers: [] }),
      })
      const data = await res.json()
      setSummary({ correctCount, total: finalAnswers.length, score, passed: score >= UNLOCK_THRESHOLD, server: data })
      if (data.adaptive_message) setAdaptiveMessage(data.adaptive_message)
      onBatchComplete?.({ correctCount, total: finalAnswers.length, score, passed: score >= UNLOCK_THRESHOLD })
      onToast?.(`Quiz submitted · ${Math.round(score * 100)}%`)
    } else {
      // Legacy LLM path: send full answer objects
      const res = await fetch(`${API}/quiz/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ topic, subtopic, score, answers: finalAnswers }),
      })
      const data = await res.json()
      setSummary({ correctCount, total: finalAnswers.length, score, passed: score >= UNLOCK_THRESHOLD, server: data })
      if (data.adaptive_message) setAdaptiveMessage(data.adaptive_message)
      onBatchComplete?.({ correctCount, total: finalAnswers.length, score, passed: score >= UNLOCK_THRESHOLD })
      onToast?.(`Quiz submitted · ${Math.round(score * 100)}%`)
    }
  }

  const nextQuestion = async () => {
    if (idx >= questions.length - 1) {
      await submitBatch([...answered])
      return
    }
    setIdx(idx + 1)
    setSelectedIndex(null)
    setServerFeedback(null)
    setFeedbackVisible(false)
  }

  if (summary) {
    const msg = summary.score >= 0.85
      ? 'Excellent! You are ready for the next concept.'
      : summary.score >= UNLOCK_THRESHOLD
        ? 'Solid progress. Let us continue.'
        : 'Let us reinforce this before moving on.'
    return (
      <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900 p-4">
        <div className="flex items-center gap-4">
          <ScoreRing score={summary.score} />
          <div>
            <p className="text-base font-semibold">
              {summary.correctCount}/{summary.total} correct — {Math.round(summary.score * 100)}%
            </p>
            <p className="mt-1 text-sm text-slate-300">{msg}</p>
          </div>
        </div>
        {adaptiveMessage && (
          <div className="mt-3 rounded-lg border border-indigo-500/30 bg-indigo-950/20 px-3 py-2 text-xs text-indigo-300">
            <TrendingUp size={12} className="mr-1 inline" />
            {adaptiveMessage}
          </div>
        )}
        <div className="mt-4 flex gap-2">
          {summary.passed ? (
            <button
              id="quiz-move-further-btn"
              onClick={onMoveFurther}
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 transition"
            >
              Move Further →
            </button>
          ) : (
            <button
              id="quiz-retry-btn"
              onClick={loadQuiz}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-indigo-300">Learning Assessment</h3>
        <span className="text-xs text-slate-400">Question {idx + 1} of {questions.length}</span>
      </div>
      <div className="mb-3 flex gap-1.5">
        {questions.map((_, i) => (
          <span
            key={i}
            className={`h-2.5 w-2.5 rounded-full ${i < answered.length ? 'bg-indigo-400' : 'border border-indigo-400/80 bg-transparent'}`}
          />
        ))}
      </div>

      <p className="mb-3 text-sm text-gray-100">{question.question}</p>
      <div className="space-y-2">
        {(question.options || []).map((op, i) => {
          // MCQ bank: highlight driven entirely by server response
          const showCorrect = isMCQ
            ? feedbackVisible && serverFeedback?.correct && i === selectedIndex
            : feedbackVisible && normalize(op) === normalize(question.correct_answer)
          const showWrong = isMCQ
            ? feedbackVisible && !serverFeedback?.correct && i === selectedIndex
            : feedbackVisible && normalize(op) === normalize(
                typeof selectedIndex === 'string' ? selectedIndex : (question.options || [])[selectedIndex] || ''
              ) && normalize(op) !== normalize(question.correct_answer)
          const isSelected = isMCQ ? i === selectedIndex : normalize(op) === normalize(
            typeof selectedIndex === 'string' ? selectedIndex : (question.options || [])[selectedIndex] || ''
          )
          return (
            <button
              key={`${op}-${i}`}
              id={`quiz-option-${i}`}
              disabled={feedbackVisible || submitting}
              onClick={() => setSelectedIndex(isMCQ ? i : op)}
              className={`w-full rounded-xl border p-3 text-left text-sm transition-all duration-300 ${
                showCorrect ? 'border-emerald-400 bg-emerald-900' :
                showWrong ? 'border-red-400 bg-red-900' :
                isSelected ? 'border-indigo-400 bg-indigo-950' :
                'border-slate-700 hover:border-indigo-400'
              } animate-[fadein_280ms_ease-out]`}
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <span className="inline-flex items-center gap-2">
                <span>{op}</span>
                {showCorrect && <Check size={14} className="text-emerald-300" />}
                {showWrong && <X size={14} className="text-red-300" />}
              </span>
            </button>
          )
        })}
      </div>

      {/* Explanation: from server response for MCQ, from question object for LLM */}
      {feedbackVisible && (
        <p className="mt-3 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
          {isMCQ ? serverFeedback?.explanation : question.explanation}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        {!feedbackVisible ? (
          <button
            id="quiz-submit-btn"
            onClick={submitCurrent}
            disabled={selectedIndex === null || submitting}
            className="rounded-lg bg-indigo-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50 hover:bg-indigo-400 transition"
          >
            {submitting ? 'Checking…' : 'Submit Answer'}
          </button>
        ) : (
          <button
            id="quiz-next-btn"
            onClick={nextQuestion}
            className="rounded-lg bg-indigo-500 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-400 transition"
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
  const [selectedIndex, setSelectedIndex] = useState(null)   // integer 0-3
  const [answered, setAnswered] = useState([])               // [{question_id, chosen_index, correct}]
  const [feedbackVisible, setFeedbackVisible] = useState(false)
  // serverFeedback: {correct: bool, explanation: str} from /quiz/mcq/submit
  const [serverFeedback, setServerFeedback] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

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
    setSelectedIndex(null)
    setAnswered([])
    setFeedbackVisible(false)
    setServerFeedback(null)
    setSummary(null)
    setLoading(false)
  }

  useEffect(() => {
    if (!open) return
    loadAssessment()
  }, [topic, subtopic, mode, open]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null
  if (loading) return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
      Preparing assessment…
    </div>
  )

  const question = questions[idx]

  // "No questions available" — skip path unchanged
  if (!question && !summary && questions.length === 0) return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 text-center space-y-3">
      <p className="text-sm font-semibold text-slate-300">No assessment items for this subtopic yet</p>
      <p className="text-xs text-slate-400">
        MCQ questions for <span className="text-indigo-300">{subtopic || topic}</span> have not been
        added to the bank yet. You can skip straight to Study.
      </p>
      <button
        id="assessment-skip-btn"
        onClick={() => onComplete?.({ skipped: true, reason: 'no_questions_available' })}
        className="rounded-lg bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400 transition"
      >
        Continue to Study &rarr;
      </button>
    </div>
  )
  if (!question && !summary) return null

  // ── Submit one MCQ answer server-side ──────────────────────────────────────
  const submitCurrent = async () => {
    if (selectedIndex === null || !question) return
    setSubmitting(true)
    try {
      const res = await fetch(`${API}/quiz/mcq/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ question_id: question.id, chosen_index: selectedIndex, context: mode }),
      })
      const data = await res.json()
      setServerFeedback(data)
      setAnswered(prev => [...prev, { question_id: question.id, chosen_index: selectedIndex, correct: data.correct }])
      setFeedbackVisible(true)
    } finally {
      setSubmitting(false)
    }
  }

  // ── After last question: send score to pretest/posttest for mastery update ─
  const submitAssessment = async (finalAnswers) => {
    const correctCount = finalAnswers.filter(a => a.correct).length
    const score = finalAnswers.length ? correctCount / finalAnswers.length : 0
    const res = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ topic, subtopic, mcq_score: score, mcq_total: finalAnswers.length }),
    })
    const data = await res.json()
    setSummary(data)
    onComplete?.(data)
    onToast?.(`${title} submitted · ${Math.round((data.score || score) * 100)}%`)
  }

  const nextQuestion = async () => {
    if (idx >= questions.length - 1) {
      await submitAssessment([...answered])
      return
    }
    setIdx(idx + 1)
    setSelectedIndex(null)
    setServerFeedback(null)
    setFeedbackVisible(false)
  }

  if (summary) {
    return (
      <div className="rounded-2xl border border-indigo-500/40 bg-indigo-950/30 p-4">
        <div className="flex items-center gap-4">
          <ScoreRing score={Number(summary.score || 0)} />
          <div>
            <p className="text-base font-semibold">
              {title} Score: {Math.round((summary.score || 0) * 100)}%
            </p>
            {mode === 'posttest' && (
              <p className="mt-1 text-sm text-slate-300">
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
    <div className="rounded-2xl border border-indigo-500/40 bg-slate-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-indigo-300">{title}</h3>
        <span className="text-xs text-slate-400">Question {idx + 1} of {questions.length}</span>
      </div>
      {/* Progress dots */}
      <div className="mb-3 flex gap-1.5">
        {questions.map((_, i) => (
          <span
            key={i}
            className={`h-2 w-2 rounded-full ${i < answered.length ? 'bg-indigo-400' : 'border border-indigo-400/60 bg-transparent'}`}
          />
        ))}
      </div>
      <p className="mb-3 text-sm text-slate-100">{question.question}</p>
      <div className="space-y-2">
        {(question.options || []).map((op, i) => {
          // Highlight driven entirely by server response — no client-side correct_answer
          const showCorrect = feedbackVisible && serverFeedback?.correct && i === selectedIndex
          const showWrong   = feedbackVisible && !serverFeedback?.correct && i === selectedIndex
          const isSelected  = i === selectedIndex
          return (
            <button
              key={`${op}-${i}`}
              id={`assessment-option-${i}`}
              disabled={feedbackVisible || submitting}
              onClick={() => setSelectedIndex(i)}
              className={`w-full rounded-xl border p-3 text-left text-sm transition ${
                showCorrect ? 'border-emerald-400 bg-emerald-900' :
                showWrong   ? 'border-red-400 bg-red-900' :
                isSelected  ? 'border-indigo-400 bg-indigo-950' :
                'border-slate-700 hover:border-indigo-400'
              }`}
            >
              <span className="inline-flex items-center gap-2">
                <span>{op}</span>
                {showCorrect && <Check size={14} className="text-emerald-300" />}
                {showWrong   && <X    size={14} className="text-red-300" />}
              </span>
            </button>
          )
        })}
      </div>
      {/* Explanation from server — only shown after submit */}
      {feedbackVisible && serverFeedback?.explanation && (
        <p className="mt-3 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
          {serverFeedback.explanation}
        </p>
      )}
      <div className="mt-3">
        {!feedbackVisible ? (
          <button
            id="assessment-submit-btn"
            onClick={submitCurrent}
            disabled={selectedIndex === null || submitting}
            className="rounded-lg bg-indigo-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50 hover:bg-indigo-400 transition"
          >
            {submitting ? 'Checking…' : 'Submit Answer'}
          </button>
        ) : (
          <button
            id="assessment-next-btn"
            onClick={nextQuestion}
            className="rounded-lg bg-indigo-500 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-400 transition"
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
                  ? 'border-indigo-500 bg-indigo-950'
                  : 'border-slate-800 bg-slate-900 hover:border-indigo-500'
              }`}
            >
              <div>
                <div className="text-sm capitalize">{t.name.replace(/_/g, ' ')}</div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-700">
                    <div
                      className="h-full bg-indigo-500 transition-all duration-500"
                      style={{ width: `${Math.round(mastery * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400">{Math.round(mastery * 100)}%</span>
                  {t.completed && (
                    <span className="rounded-full bg-emerald-800 px-1.5 py-0.5 text-[10px] text-emerald-200">
                      ✓
                    </span>
                  )}
                </div>
              </div>
              {isExpanded ? (
                <ChevronDown size={14} className="shrink-0 text-slate-400" />
              ) : (
                <ChevronRight size={14} className="shrink-0 text-slate-400" />
              )}
            </button>

            {/* Subtopic list */}
            {isExpanded && (t.subtopics || []).length > 0 && (
              <div className="ml-3 mt-1 space-y-0.5 border-l border-slate-700 pl-3">
                {t.subtopics.map((sub) => {
                  const isActiveSub = currentSubtopic === sub.id
                  return (
                    <button
                      key={sub.id}
                      id={`subtopic-btn-${sub.id}`}
                      onClick={() => onSelectSubtopic(t.name, sub.id)}
                      className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs transition ${
                        isActiveSub
                          ? 'bg-indigo-900 text-indigo-200'
                          : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                      }`}
                    >
                      <span className="truncate">{sub.title}</span>
                      {sub.passed && <Check size={10} className="ml-1 shrink-0 text-emerald-400" />}
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
    setAssessmentOpen(false)  // Close assessment when switching topics/subtopics
    setContentReady(false)
    setMessages([])  // Clear messages to prevent showing old topic content
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

  // Per-subtopic pretest / posttest tracking — check assessment_scores keyed by topic + subtopic
  const currentSubtopicAssessment = useMemo(() => {
    if (!selectedTopic || !currentSubtopic) return { pretestDone: false, posttestDone: false, pretestScore: null, posttestScore: null }
    
    const scores = studentState?.assessment_scores || {}
    const topicMap = scores[selectedTopic] || {}
    const subtopicEntry = topicMap[currentSubtopic] || {}
    
    return {
      pretestDone: subtopicEntry?.pretest_score !== null && subtopicEntry?.pretest_score !== undefined,
      posttestDone: subtopicEntry?.posttest_score !== null && subtopicEntry?.posttest_score !== undefined,
      pretestScore: subtopicEntry?.pretest_score || null,
      posttestScore: subtopicEntry?.posttest_score || null,
    }
  }, [studentState, selectedTopic, currentSubtopic])

  const pretestDoneForTopic = currentSubtopicAssessment.pretestDone
  const posttestDoneForTopic = currentSubtopicAssessment.posttestDone
  
  // Allow retaking pretest - show "Retake Pre-Test" button if already completed
  const canRetakePretest = pretestDoneForTopic && currentSubtopicAssessment.pretestScore !== null

  // Check if all subtopics of current topic have been practiced (for post-test eligibility)
  const currentTopicData = topics.find(t => t.name === selectedTopic)
  const allSubtopicsPracticed = (currentTopicData?.subtopics || []).length > 0 &&
    (currentTopicData?.subtopics || []).every(sub => sub.passed || sub.attempts > 0)
  
  // Show post-test when: pre-test done, all subtopics practiced, and post-test not yet taken
  const showPostTest = pretestDoneForTopic && allSubtopicsPracticed && !posttestDoneForTopic

  return (
    <div className="h-screen overflow-hidden bg-[#0a0a16] font-[Inter,system-ui] text-slate-100">
      {/* Top bar */}
      <div className="w-full border-b-2 border-indigo-700 bg-slate-900 px-3 py-2">
        <div className="flex items-center justify-between">
          {/* Left: progress info */}
          <div className="text-xs text-slate-300">
            Session Progress · {cycles} cycles · {status}
            {studentState?.level && (
              <span className="ml-2 rounded-full border border-indigo-500/50 px-2 py-0.5 text-indigo-300">
                {studentState.level}
              </span>
            )}
          </div>
          {/* Right: user badge + logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800 px-3 py-1">
              <User size={12} className="text-indigo-400" />
              <span className="text-xs text-slate-300 max-w-[140px] truncate">{userName}</span>
            </div>
            <button
              id="logout-btn"
              onClick={logout}
              className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-400 transition-colors hover:border-red-500/50 hover:bg-red-950/30 hover:text-red-400"
              title="Sign out"
            >
              <LogOut size={12} />
              Sign out
            </button>
          </div>
        </div>
        {/* Progress bar */}
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {toast && (
        <div className="fixed right-4 top-4 z-50 rounded-lg border border-indigo-500 bg-slate-900 px-4 py-2 text-sm text-indigo-300 shadow-lg">
          {toast}
        </div>
      )}

      <div className="flex h-[calc(100vh-66px)]">
        {/* Sidebar — Issue #5 fix: full topic tree */}
        <aside className="w-[300px] shrink-0 overflow-y-auto border-r border-slate-800 bg-gradient-to-b from-slate-900 to-[#0a0a18] p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-indigo-300">Topics</h2>
          <TopicSidebar
            topics={topics}
            selectedTopic={selectedTopic}
            currentSubtopic={currentSubtopic}
            onSelectSubtopic={handleSelectSubtopic}
          />

          {heatmap.length > 0 && (
            <>
              <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wider text-indigo-300">Mastery Heatmap</h3>
              <div className="space-y-2">
                {heatmap.map((c) => (
                  <div key={c.name} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900 px-2 py-2">
                    <span className="text-xs capitalize text-slate-300">{c.name.replace(/_/g, ' ')}</span>
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
        <main className="flex-1 bg-[#080814] p-4">
          {/* ── Topic header + action toolbar ─────────────────────────────── */}
          <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
            <div>
              <h1 className="text-sm font-semibold tracking-tight text-slate-200">
                {selectedTopic
                  ? `${selectedTopic.replace(/_/g, ' ')}${currentSubtopic ? ` › ${currentSubtopic}` : ''}`
                  : 'Select a topic to begin'}
              </h1>
              {/* Progressive flow indicator */}
              {selectedTopic && (
                <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
                  <span className={pretestDoneForTopic ? 'text-emerald-400 font-semibold' : 'text-amber-400 font-semibold'}>
                    1. Pre-Test{pretestDoneForTopic ? ' ✓' : ''}{canRetakePretest ? ' (retake available)' : ''}
                  </span>
                  <span>→</span>
                  <span className={contentReady || messages.some(m => m.role === 'tutor' && m.text) ? 'text-indigo-400 font-semibold' : 'text-slate-600'}>
                    2. Study
                  </span>
                  <span>→</span>
                  <span className="text-slate-600">3. Practice Quiz</span>
                  <span>→</span>
                  <span className={posttestDoneForTopic ? 'text-emerald-400 font-semibold' : 'text-slate-600'}>
                    4. Post-Test{posttestDoneForTopic ? ' ✓' : ''}
                  </span>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              {/* Step 1: Pre-Test — show if pretest not done */}
              {selectedTopic && !pretestDoneForTopic && (
                <button
                  id="pretest-btn"
                  onClick={() => openAssessment('pretest')}
                  disabled={streaming}
                  className="flex items-center gap-1.5 rounded-lg border border-amber-500 bg-amber-950/40 px-4 py-2 text-xs font-semibold text-amber-300 disabled:opacity-50 hover:bg-amber-900/50 transition animate-pulse"
                >
                  📋 Take Pre-Test
                </button>
              )}
              
              {/* Pretest done badge with score and retake option */}
              {selectedTopic && pretestDoneForTopic && (
                <div className="flex items-center gap-2">
                  <span className="rounded-lg border border-emerald-600/50 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-400 font-medium">
                    ✓ Pre-Test Done {currentSubtopicAssessment.pretestScore !== null && `(${Math.round(currentSubtopicAssessment.pretestScore * 100)}%)`}
                  </span>
                  <button
                    id="retake-pretest-btn"
                    onClick={() => openAssessment('pretest')}
                    disabled={streaming}
                    className="rounded-lg border border-slate-600 bg-slate-800/50 px-3 py-2 text-xs text-slate-300 disabled:opacity-50 hover:bg-slate-700/50 transition"
                    title="Retake pre-test to improve your score and get adaptive content"
                  >
                    🔄 Retake
                  </button>
                </div>
              )}
              
              {/* Step 2: Study content — show after pretest */}
              {selectedTopic && pretestDoneForTopic && (
                <button
                  id="explain-btn"
                  onClick={startStream}
                  disabled={!selectedTopic || streaming}
                  className="rounded-lg bg-indigo-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50 hover:bg-indigo-400 transition"
                >
                  {streaming ? 'Generating…' : `Explain ${selectedTopic ? selectedTopic.replace(/_/g, ' ') : ''}`}
                </button>
              )}
              {/* Step 2 fallback: show explain button even before pretest (so user isn't blocked) */}
              {selectedTopic && !pretestDoneForTopic && (
                <button
                  id="explain-btn-skip"
                  onClick={startStream}
                  disabled={!selectedTopic || streaming}
                  title="You can study first, or take the pre-test to track your improvement"
                  className="rounded-lg border border-slate-600 px-4 py-2 text-xs text-slate-400 disabled:opacity-50 hover:border-slate-500 transition"
                >
                  {streaming ? 'Generating…' : 'Skip Pre-Test & Study'}
                </button>
              )}
              {/* Step 3: Learning Assessment — after content is ready */}
              {contentReady && !quizOpen && (
                <button
                  id="start-quiz-btn"
                  onClick={openQuiz}
                  disabled={!selectedTopic || streaming}
                  className="rounded-lg border border-indigo-500 px-4 py-2 text-xs font-semibold text-indigo-300 disabled:opacity-50 hover:bg-indigo-950 transition"
                >
                  🎯 Practice Quiz
                </button>
              )}
              {/* Step 4: Post-Test — shows when all subtopics practiced */}
              {showPostTest && (
                <button
                  id="posttest-btn-ready"
                  onClick={() => openAssessment('posttest')}
                  disabled={streaming}
                  className="flex items-center gap-1.5 rounded-lg border border-emerald-500 bg-emerald-950/40 px-4 py-2 text-xs font-semibold text-emerald-300 disabled:opacity-50 hover:bg-emerald-900/50 transition"
                >
                  📋 Take Post-Test
                </button>
              )}
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
                      <div className="mb-1 flex items-center gap-2 text-xs text-indigo-300">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-indigo-500/20 shadow-[0_0_16px_rgba(99,102,241,0.4)]">
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
                <div className="rounded-2xl border border-emerald-500/40 bg-emerald-950/40 p-4">
                  <p className="text-base font-semibold tracking-tight text-emerald-300">Topic Complete 🎉</p>
                  <p className="mt-1 text-sm text-slate-300">
                    You have finished all subtopics for {selectedTopic?.replace(/_/g, ' ')}.
                    The next topic is now unlocked.
                  </p>
                  <button
                    id="posttest-btn"
                    onClick={() => openAssessment('posttest')}
                    className="mt-4 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 transition"
                  >
                    Take Complete Assessment
                  </button>
                </div>
              )}

              {studentState?.posttest_score !== null && studentState?.posttest_score !== undefined && (
                <>
                  <div className="rounded-2xl border border-indigo-500/40 bg-slate-900 p-4 text-sm text-slate-300">
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
