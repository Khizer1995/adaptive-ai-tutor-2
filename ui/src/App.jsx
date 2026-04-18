import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import ReactMarkdown from 'react-markdown'
import { useState, useEffect } from 'react'
import './index.css'

const API = 'http://localhost:8000'

// ── HELPERS ──────────────────────────────────────────────────────
function optionLabelToIndex(value) {
  if (typeof value !== 'string') return -1
  const trimmed = value.trim().toUpperCase()
  if (trimmed.length === 1 && trimmed >= 'A' && trimmed <= 'Z') {
    return trimmed.charCodeAt(0) - 65
  }
  return -1
}

function normalizeAnswerValue(value, options) {
  if (value == null) return ''
  const raw = String(value).trim()
  const idx = optionLabelToIndex(raw)
  if (idx >= 0 && idx < options.length) {
    const resolved = options[idx]
    return String(resolved?.text ?? resolved ?? '').trim()
  }
  return raw
}

function getMasteryColor(value) {
  if (value >= 0.7) return '#39d353'
  if (value >= 0.4) return '#f0883e'
  return '#f85149'
}

function getMasteryLabel(value) {
  if (value >= 0.7) return 'Mastered'
  if (value >= 0.4) return 'Learning'
  return 'Not started'
}

// ── SIDEBAR ──────────────────────────────────────────────────────
function Sidebar({ selectedTopic, onSelect, topics, loading }) {
  return (
    <div className="w-60 bg-gray-800 border-r border-gray-700 flex flex-col flex-shrink-0">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-xs uppercase tracking-widest text-gray-500">
          Learning Memory
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="p-4 text-xs text-gray-500">Loading topics...</div>
        ) : topics.length === 0 ? (
          <div className="p-4 text-xs text-gray-500">No topics found</div>
        ) : (
          topics.map(topic => {
            const pct = Math.round(topic.mastery * 100)
            const color = getMasteryColor(topic.mastery)
            const isActive = selectedTopic?.name === topic.name
            return (
              <div
                key={topic.name}
                onClick={() => onSelect(topic)}
                className={`p-3 rounded-lg cursor-pointer mb-1 border transition-all ${
                  isActive
                    ? 'bg-gray-700 border-gray-600'
                    : 'border-transparent hover:bg-gray-700'
                }`}
              >
                <div className="text-xs font-medium text-gray-200 mb-2 capitalize">
                  {topic.name}
                </div>
                <div className="h-1 rounded-full bg-gray-900 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-xs" style={{ color }}>
                    {getMasteryLabel(topic.mastery)}
                  </span>
                  <span className="text-xs text-gray-500">{pct}%</span>
                </div>
              </div>
            )
          })
        )}
      </div>

      {selectedTopic && (
        <div className="p-4 border-t border-gray-700 bg-gray-900">
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-3 capitalize">
            {selectedTopic.name}
          </div>
          <div className="flex justify-between text-xs mb-2">
            <span className="text-gray-500">Mastery</span>
            <span style={{ color: getMasteryColor(selectedTopic.mastery) }}>
              {Math.round(selectedTopic.mastery * 100)}%
            </span>
          </div>
          <div className="flex justify-between text-xs mb-2">
            <span className="text-gray-500">Confidence</span>
            <span className="text-gray-300">
              {Math.round((selectedTopic.confidence || 0) * 100)}%
            </span>
          </div>
          <div className="flex justify-between text-xs mb-3">
            <span className="text-gray-500">Attempts</span>
            <span className="text-gray-300">{selectedTopic.attempts || 0}</span>
          </div>
          {selectedTopic.weak_areas?.length > 0 && (
            <>
              <div className="text-xs text-gray-500 mb-2">Weak areas</div>
              <div className="flex flex-wrap gap-1">
                {selectedTopic.weak_areas.map(w => (
                  <span
                    key={w}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: 'rgba(248,81,73,0.15)', color: '#f85149' }}
                  >
                    {w}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── QUIZ PANEL ───────────────────────────────────────────────────
function QuizPanel({ topic, onAnswerSubmit }) {
  const [questions, setQuestions] = useState([])
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!topic) return
    setLoading(true)
    fetch(`${API}/quiz/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic.name })
    })
      .then(r => r.json())
      .then(data => {
        setQuestions(data.questions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [topic])

  const handleSubmit = async () => {
    if (!selected) return
    const q = questions[current]
    const options = q.options || q.choices || []
    const resolvedCorrectAnswer = normalizeAnswerValue(q.correct_answer || q.answer || '', options)
    const resolvedSelectedAnswer = normalizeAnswerValue(selected, options)
    const res = await fetch(`${API}/quiz/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q.question || q,
        selected_answer: resolvedSelectedAnswer,
        correct_answer: resolvedCorrectAnswer,
        topic: topic.name,
      })
    })
    const data = await res.json()
    setResult(data)
    setSubmitted(true)
    if (onAnswerSubmit) onAnswerSubmit(data)
  }

  if (loading) return (
    <div className="flex items-center gap-2 text-xs text-gray-500 p-4">
      <div className="w-3 h-3 rounded-full border border-gray-500 border-t-transparent animate-spin" />
      Generating quiz for {topic?.name}...
    </div>
  )

  if (!questions.length) return (
    <div className="text-xs text-gray-500 p-4">
      No quiz questions available for this topic yet.
    </div>
  )

  const q = questions[current]
  const options = q.options || q.choices || []
  const normalizedCorrectAnswer = normalizeAnswerValue(q.correct_answer || q.answer || '', options)
  const normalizedSelectedAnswer = normalizeAnswerValue(selected, options)
  const isCorrect = result?.correct

  const getOptionStyle = (optId) => {
    const normalizedOption = normalizeAnswerValue(optId, options)
    if (!submitted) {
      return selected === optId
        ? 'border-blue-500 bg-blue-500/10'
        : 'border-gray-700 hover:border-gray-500'
    }
    if (normalizedOption === normalizedCorrectAnswer) return 'border-green-500 bg-green-500/10'
    if (normalizedOption === normalizedSelectedAnswer && !isCorrect) return 'border-red-500 bg-red-500/10'
    return 'border-gray-700 opacity-40'
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-xs uppercase tracking-widest text-gray-500">
          Quiz · {topic?.name}
        </span>
        <div className="flex-1 h-px bg-gray-700" />
        <span className="text-xs text-gray-600">
          {current + 1} / {questions.length}
        </span>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-lg p-5 mb-4">
        <div className="text-sm font-medium text-gray-200 mb-3 leading-relaxed">
          {q.question || q}
        </div>
        {q.code && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 font-mono text-xs leading-loose text-green-400">
            {q.code}
          </div>
        )}
      </div>

      <div className="space-y-2 mb-4">
        {options.map((opt, i) => {
          const optId = typeof opt === 'string' ? opt : opt.id || String(i)
          const optText = typeof opt === 'string' ? opt : opt.text || opt
          return (
            <div
              key={optId}
              onClick={() => !submitted && setSelected(optId)}
              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${getOptionStyle(optId)}`}
            >
              <div className="w-6 h-6 rounded bg-gray-800 flex items-center justify-center text-xs font-semibold text-gray-400 flex-shrink-0">
                {String.fromCharCode(65 + i)}
              </div>
              <span className="text-sm text-gray-300">{optText}</span>
            </div>
          )
        })}
      </div>

      {!submitted ? (
        <button
          onClick={handleSubmit}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${
            selected
              ? 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'
              : 'bg-gray-700 text-gray-500 cursor-not-allowed'
          }`}
        >
          Submit Answer
        </button>
      ) : (
        <div className={`rounded-lg border p-4 mt-2 ${
          isCorrect ? 'border-green-600 bg-green-500/10' : 'border-red-600 bg-red-500/10'
        }`}>
          <div className={`text-sm font-semibold mb-2 ${isCorrect ? 'text-green-400' : 'text-red-400'}`}>
            {isCorrect ? '✓ Correct!' : '✗ Not quite right'}
          </div>
          {q.explanation && (
            <div className="text-xs text-gray-400 leading-relaxed mb-3">
              {q.explanation}
            </div>
          )}
          {!isCorrect && q.hint && (
            <div className="border-l-2 border-amber-500 pl-3 py-1 mb-3">
              <span className="text-xs text-amber-400">Hint: {q.hint}</span>
            </div>
          )}
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => { setSelected(null); setSubmitted(false); setResult(null) }}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-lg border border-gray-600 transition-colors"
            >
              Try Again
            </button>
            {current < questions.length - 1 && (
              <button
                onClick={() => {
                  setCurrent(c => c + 1)
                  setSelected(null)
                  setSubmitted(false)
                  setResult(null)
                }}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
              >
                Next Question →
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── VIZ PANEL ────────────────────────────────────────────────────
function VizPanel({ onClose, topic }) {
  const [vizTab, setVizTab] = useState('stack')
  const [stackFrames, setStackFrames] = useState(['main()'])
  const [stepIndex, setStepIndex] = useState(0)

  const STEPS = [
    { label: `Call ${topic?.name || 'function'}()`, action: () => setStackFrames(s => [`${topic?.name || 'fn'}()`, ...s]) },
    { label: 'Push local variables', action: () => setStackFrames(s => ['local vars', ...s]) },
    { label: 'Execute return', action: () => setStackFrames(s => ['→ return value', ...s]) },
    { label: 'Pop return value', action: () => setStackFrames(s => s.slice(1)) },
    { label: 'Pop frame', action: () => setStackFrames(s => s.slice(1)) },
    { label: 'Reset', action: () => { setStackFrames(['main()']); setStepIndex(-1) } },
  ]

  const handleStep = () => {
    const i = stepIndex % STEPS.length
    STEPS[i].action()
    setStepIndex(i + 1)
  }

  return (
    <div className="w-72 bg-gray-800 border-l border-gray-700 flex flex-col flex-shrink-0">
      <div className="p-4 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-gray-500">Visualization</h3>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-300 text-sm px-2 py-0.5 rounded hover:bg-gray-700 transition-colors"
        >
          ✕
        </button>
      </div>

      <div className="flex gap-1 p-2 border-b border-gray-700">
        {['stack', 'concept'].map(tab => (
          <button
            key={tab}
            onClick={() => setVizTab(tab)}
            className={`px-3 py-1 rounded text-xs transition-all ${
              vizTab === tab ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab === 'stack' ? 'Call Stack' : 'Concept Map'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {vizTab === 'stack' && (
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-widest mb-4">
              Call stack · {topic?.name}
            </div>
            <div className="text-center text-xs text-gray-600 mb-2">▲ TOP</div>
            <div className="flex flex-col gap-2 mb-4">
              {stackFrames.map((frame, i) => (
                <div
                  key={frame + i}
                  className={`px-4 py-2.5 rounded-lg border text-xs text-center font-mono transition-all ${
                    i === 0
                      ? 'border-green-600 bg-green-500/10 text-green-400'
                      : 'border-gray-600 text-gray-400'
                  }`}
                >
                  {frame}
                </div>
              ))}
              <div className="text-center text-xs text-gray-700 mt-1">Stack base</div>
            </div>
            <button
              onClick={handleStep}
              className="w-full py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-lg border border-gray-600 transition-colors"
            >
              {stepIndex < STEPS.length
                ? `▶  ${STEPS[stepIndex % STEPS.length].label}`
                : '▶  Step →'}
            </button>
          </div>
        )}

        {vizTab === 'concept' && (
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-widest mb-4 capitalize">
              Concept map · {topic?.name}
            </div>
            <div className="flex flex-col items-center gap-3">
              <div className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-500/10 text-blue-400 text-xs text-center w-full capitalize">
                {topic?.name}
              </div>
              <div className="text-gray-600 text-xs">↓</div>
              <div className="grid grid-cols-2 gap-2 w-full">
                {(topic?.weak_areas?.length > 0
                  ? topic.weak_areas
                  : ['core concepts', 'applications']
                ).map(concept => (
                  <div
                    key={concept}
                    className="px-2 py-2 rounded-lg border border-amber-700 bg-amber-500/10 text-amber-400 text-xs text-center capitalize"
                  >
                    {concept}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-xs text-gray-600 text-center">
                Amber = weak areas to focus on
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
// ── PROGRESS CHARTS ──────────────────────────────────────────────
function ProgressCharts({ studentState, topics }) {
  const gainHistory = studentState?.learning_gain_history || []
  const accuracyHistory = studentState?.accuracy_history || []

  const gainData = gainHistory.slice(-10).map((v, i) => ({
    session: `S${i + 1}`,
    gain: parseFloat((v * 100).toFixed(1)),
  }))

  const accuracyData = accuracyHistory.slice(-10).map((v, i) => ({
    session: `S${i + 1}`,
    accuracy: parseFloat((v * 100).toFixed(1)),
  }))

  const topicData = topics.map(t => ({
    name: t.name.split(' ')[0],
    mastery: Math.round(t.mastery * 100),
    confidence: Math.round((t.confidence || 0) * 100),
  }))

  return (
    <div className="w-80 bg-gray-800 border-l border-gray-700 flex flex-col flex-shrink-0">
      <div className="p-4 border-b border-gray-700">
        <h3 className="text-xs uppercase tracking-widest text-gray-500">
          Progress Analytics
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">

        {/* Mastery per topic */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">
            Topic Mastery
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={topicData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: 6,
                  fontSize: 11
                }}
                formatter={v => `${v}%`}
              />
              <Bar dataKey="mastery" fill="#39d353" radius={[3, 3, 0, 0]} />
              <Bar dataKey="confidence" fill="#58a6ff" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-3 mt-2">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs text-gray-500">Mastery</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-xs text-gray-500">Confidence</span>
            </div>
          </div>
        </div>

        {/* Learning gain history */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">
            Learning Gain (last 10 sessions)
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={gainData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="session" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: 6,
                  fontSize: 11
                }}
                formatter={v => `${v}%`}
              />
              <Line
                type="monotone"
                dataKey="gain"
                stroke="#f0883e"
                strokeWidth={2}
                dot={{ r: 3, fill: '#f0883e' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Accuracy history */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">
            Accuracy over time
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={accuracyData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="session" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: 6,
                  fontSize: 11
                }}
                formatter={v => `${v}%`}
              />
              <Line
                type="monotone"
                dataKey="accuracy"
                stroke="#58a6ff"
                strokeWidth={2}
                dot={{ r: 3, fill: '#58a6ff' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Student summary */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">
            Student Summary
          </div>
          <div className="space-y-2">
            {[
              { label: 'Student ID', value: studentState?.student_id || '—' },
              { label: 'Level', value: studentState?.level || '—' },
              { label: 'Engagement', value: studentState?.engagement || '—' },
              { label: 'Last Score', value: `${Math.round((studentState?.last_score || 0) * 100)}%` },
              { label: 'Current Topic', value: studentState?.current_topic || '—' },
            ].map(item => (
              <div key={item.label} className="flex justify-between text-xs">
                <span className="text-gray-500">{item.label}</span>
                <span className="text-gray-300 capitalize">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

// ── CENTER PANEL ─────────────────────────────────────────────────
function CenterPanel({ topic, studentState, onStateUpdate, onShowCharts, showCharts, onSelectTopic }) {
  const [mode, setMode] = useState('concept')
  const [showExample, setShowExample] = useState(false)
  const [vizOpen, setVizOpen] = useState(false)
  const [content, setContent] = useState(null)
  const [loadingContent, setLoadingContent] = useState(false)

  // Fetch real explanation from Tutor Agent when topic changes
  useEffect(() => {
    if (!topic) return
    setLoadingContent(true)
    setMode('concept')
    setContent(null)
    fetch(`${API}/tutor/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic.name })
    })
      .then(r => r.json())
      .then(data => {
        setContent(data)
        setLoadingContent(false)
      })
      .catch(() => setLoadingContent(false))
  }, [topic])

  const handleAnswerSubmit = () => {
  if (onStateUpdate) {
    onStateUpdate().then(() => {
      // State refreshed — sidebar will re-render with new mastery values
      console.log('Student state refreshed after quiz answer')
    })
  }
}

  const engagementColor = {
    low: '#f85149',
    medium: '#f0883e',
    high: '#39d353'
  }[studentState?.engagement] || '#f0883e'

  const masteryPct = topic
    ? Math.round((topic.mastery || 0) * 100)
    : Math.round((studentState?.last_score || 0) * 100)

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="p-4 border-b border-gray-700 bg-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-gray-900 p-1 rounded-lg">
              {['concept', 'quiz'].map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`px-3 py-1 rounded-md text-xs transition-all ${
                    mode === m ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {m === 'concept' ? 'Learn' : 'Quiz'}
                </button>
              ))}
            </div>
            <span className="text-xs text-gray-500 capitalize">
              {topic?.name || 'Select a topic'} · {studentState?.level || 'beginner'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ background: engagementColor }} />
              <span className="text-xs text-gray-400 capitalize">
                Engagement: {studentState?.engagement || 'medium'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ background: getMasteryColor(masteryPct / 100) }} />
              <span className="text-xs text-gray-400">Mastery {masteryPct}%</span>
            </div>
            <button
              onClick={onShowCharts}
              className={`px-3 py-1 text-xs rounded-lg border transition-colors ${
                showCharts
                  ? 'border-blue-500 text-blue-400 bg-blue-500/10'
                  : 'border-gray-600 text-gray-400 hover:border-gray-500'
  }`}
>
  {showCharts ? 'Hide Graph' : 'Show Graph'}
</button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {!topic ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-gray-600 text-sm mb-2">← Select a topic from the sidebar</div>
              <div className="text-gray-700 text-xs">
                The tutor will generate personalized content based on your mastery level
              </div>
            </div>
          ) : mode === 'concept' ? (
            <div>
              {/* Why this content */}
              {content?.macro_decision?.reason && (
                <div className="border-l-2 border-purple-500 pl-4 mb-5 bg-gray-900 py-3 pr-4 rounded-r-lg">
                  <div className="text-xs uppercase tracking-widest text-purple-400 mb-1">
                    Why this content?
                  </div>
                  <div className="text-xs text-gray-400 leading-relaxed">
                    {content.macro_decision.reason}
                  </div>
                </div>
              )}

              {/* Section label */}
              <div className="flex items-center gap-3 mb-4">
                <span className="text-xs uppercase tracking-widest text-gray-500 capitalize">
                  Explanation · {topic.name}
                </span>
                <div className="flex-1 h-px bg-gray-700" />
              </div>

              {/* Content from Tutor Agent */}
              {loadingContent ? (
  <div className="flex flex-col gap-4 mb-4">
    <div className="flex items-center gap-3 p-4 bg-gray-800 border border-gray-700 rounded-lg">
      <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin flex-shrink-0" />
      <div>
        <div className="text-xs text-blue-400 font-medium mb-0.5">
          Tutor Agent is generating content...
        </div>
        <div className="text-xs text-gray-500">
          Personalizing explanation for your level
        </div>
      </div>
    </div>
    {/* Skeleton lines */}
    <div className="space-y-2">
      {[100, 90, 95, 75, 88].map((w, i) => (
        <div
          key={i}
          className="h-3 bg-gray-800 rounded animate-pulse"
          style={{ width: `${w}%` }}
        />
      ))}
    </div>
  </div>
) : (
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-5 mb-4 text-sm text-gray-300 leading-relaxed prose prose-invert prose-sm max-w-none">
  <ReactMarkdown>
    {content?.learning_path || 'Loading content from tutor agent...'}
  </ReactMarkdown>
</div>
              )}

              {/* RAG chunks if available */}
              {content?.rag_chunks?.length > 0 && showExample && (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 mb-4">
                  <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">
                    Source material
                  </div>
                  {content.rag_chunks.slice(0, 2).map((chunk, i) => (
                    <div key={i} className="text-xs text-gray-400 leading-relaxed mb-2 border-l-2 border-gray-700 pl-3">
                      {typeof chunk === 'string' ? chunk : chunk.text || JSON.stringify(chunk)}
                    </div>
                  ))}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => setMode('quiz')}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors font-medium"
                >
                  Try Quiz
                </button>
                <button
                  onClick={() => setShowExample(v => !v)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-lg transition-colors border border-gray-600"
                >
                  {showExample ? 'Hide Sources' : 'Show Sources'}
                </button>
                <button
                  onClick={() => setVizOpen(true)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-purple-400 text-xs rounded-lg transition-colors border border-purple-800"
                >
                  Visualize
                </button>
              </div>
              {content?.next_recommendation && (
                <div className="mt-4 bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <div className="text-xs uppercase tracking-widest text-blue-400 mb-1">
                    Next Recommendation
                  </div>
                  <div className="text-sm text-gray-200 mb-1 capitalize">
                    {content.next_recommendation.label}: {content.next_recommendation.topic} · {content.next_recommendation.concept}
                  </div>
                  <div className="text-xs text-gray-400 mb-3">
                    {content.next_recommendation.reason}
                  </div>
                  <button
                    onClick={() => onSelectTopic && onSelectTopic(content.next_recommendation.topic)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors font-medium"
                  >
                    Continue Learning →
                  </button>
                </div>
              )}
            </div>
          ) : (
            <QuizPanel
              topic={topic}
              onAnswerSubmit={handleAnswerSubmit}
            />
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-2 border-t border-gray-700 bg-gray-900 flex gap-6">
          {[
            { label: 'Level', value: studentState?.level || 'beginner' },
            { label: 'Score', value: `${Math.round((studentState?.last_score || 0) * 100)}%` },
            {
              label: 'Decision',
              value: studentState?.macro_decision?.action || 'loading...',
              color: 'text-blue-400'
            },
            { label: 'Topic', value: studentState?.current_topic || '—' },
          ].map(item => (
            <div key={item.label} className="flex flex-col gap-0.5">
              <span className="text-xs text-gray-600 uppercase tracking-widest">{item.label}</span>
              <span className={`text-xs font-medium capitalize ${item.color || 'text-gray-300'}`}>
                {item.value}
              </span>
            </div>
          ))}
        </div>

      </div>

      {vizOpen && <VizPanel onClose={() => setVizOpen(false)} topic={topic} />}
    </div>
  )
}

// ── APP ROOT ─────────────────────────────────────────────────────
function App() {
  const [selectedTopic, setSelectedTopic] = useState(null)
  const [topics, setTopics] = useState([])
  const [studentState, setStudentState] = useState(null)
  const [loadingTopics, setLoadingTopics] = useState(true)
  const [showCharts, setShowCharts] = useState(false)
  const fetchStudentData = () => {
  return Promise.all([
    fetch(`${API}/student/state`).then(r => r.json()),
    fetch(`${API}/student/topics`).then(r => r.json()),
  ]).then(([stateData, topicsData]) => {
    setStudentState(stateData)
    setTopics(topicsData.topics || [])
    setLoadingTopics(false)
  })
}

  const handleSelectTopicByName = (topicName) => {
    if (!topicName) return
    const existing = topics.find(t => t.name === topicName)
    if (existing) {
      setSelectedTopic(existing)
      return
    }
    fetch(`${API}/student/topics`)
      .then(r => r.json())
      .then(data => {
        const refreshedTopics = data.topics || []
        setTopics(refreshedTopics)
        const found = refreshedTopics.find(t => t.name === topicName)
        if (found) {
          setSelectedTopic(found)
        } else {
          setSelectedTopic({
            name: topicName,
            mastery: 0,
            confidence: 0,
            attempts: 0,
            weak_areas: []
          })
        }
      })
      .catch(() => {
        setSelectedTopic({
          name: topicName,
          mastery: 0,
          confidence: 0,
          attempts: 0,
          weak_areas: []
        })
      })
  }

  useEffect(() => {
    fetchStudentData()
  }, [])

  return (
  <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
    <Sidebar
      selectedTopic={selectedTopic}
      onSelect={setSelectedTopic}
      topics={topics}
      loading={loadingTopics}
    />
    <CenterPanel
      topic={selectedTopic}
      studentState={studentState}
      onStateUpdate={fetchStudentData}
      onShowCharts={() => setShowCharts(v => !v)}
      showCharts={showCharts}
      onSelectTopic={handleSelectTopicByName}
    />
    {showCharts && (
      <ProgressCharts
        studentState={studentState}
        topics={topics}
      />
    )}
  </div>
)}

export default App
