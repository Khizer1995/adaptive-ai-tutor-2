import { useMemo, useState } from 'react'

const SECTIONS = [
  {
    title: 'Usability',
    subtitle: 'SUS-inspired',
    items: [
      ['usability_easy_to_use', 'The system was easy to use'],
      ['usability_clear_explanations', 'The explanations were clear and understandable'],
      ['usability_quiz_alignment', 'The quizzes matched what I just learned'],
      ['usability_adapted_level', 'The system felt like it adapted to my level'],
      ['usability_use_again', 'I would use this system again to learn a new topic'],
    ],
  },
  {
    title: 'Trust',
    items: [
      ['trust_explanations', "I trusted the system's explanations"],
      ['trust_hints', 'The system gave me appropriate hints'],
      ['trust_learning_needs', 'I felt the system understood my learning needs'],
    ],
  },
  {
    title: 'Engagement',
    items: [
      ['engagement_throughout', 'I was engaged throughout the session'],
      ['engagement_difficulty', 'The difficulty felt appropriate for me'],
      ['engagement_progress', 'I felt I made progress'],
    ],
  },
]

const LIKERT = [1, 2, 3, 4, 5]

export default function StudyQuestionnaire({
  apiBase,
  topic,
  subtopic,
  studentId,
  onSubmitted,
  onToast,
}) {
  const [responses, setResponses] = useState({})
  const [likedMost, setLikedMost] = useState('')
  const [improve, setImprove] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const questionCount = useMemo(
    () => SECTIONS.reduce((total, section) => total + section.items.length, 0),
    [],
  )
  const complete = Object.keys(responses).length === questionCount

  const submitSurvey = async () => {
    if (!complete || submitting) return
    setSubmitting(true)
    setError('')

    try {
      const res = await fetch(`${apiBase}/study/survey`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          topic,
          subtopic,
          responses,
          liked_most: likedMost,
          improve,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Survey submission failed')
      setSubmitted(true)
      onSubmitted?.(data)
      onToast?.('Study survey submitted. Thank you!')
    } catch (err) {
      setError(err.message || 'Survey submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="rounded-2xl border border-green-500/40 bg-green-950/30 p-4 text-sm text-green-200">
        Study survey submitted. These responses are ready for Table 2 aggregation.
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-purple-500/40 bg-gray-900 p-4">
      <div className="mb-4">
        <p className="text-base font-semibold text-purple-200">Post-session Study Questionnaire</p>
        <p className="mt-1 text-sm text-gray-400">Rate each item from 1 (strongly disagree) to 5 (strongly agree).</p>
      </div>

      <div className="space-y-5">
        {SECTIONS.map((section) => (
          <section key={section.title} className="rounded-xl border border-gray-800 bg-gray-950/40 p-3">
            <div className="mb-3 flex items-baseline gap-2">
              <h3 className="text-sm font-semibold text-teal-300">{section.title}</h3>
              {section.subtitle && <span className="text-xs text-gray-500">{section.subtitle}</span>}
            </div>
            <div className="space-y-3">
              {section.items.map(([id, label]) => (
                <div key={id} className="grid gap-2 md:grid-cols-[1fr_auto] md:items-center">
                  <p className="text-sm text-gray-200">{label}</p>
                  <div className="flex gap-1">
                    {LIKERT.map((value) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setResponses((current) => ({ ...current, [id]: value }))}
                        className={`h-8 w-8 rounded-lg border text-xs font-semibold transition ${
                          responses[id] === value
                            ? 'border-purple-300 bg-purple-500 text-gray-950'
                            : 'border-gray-700 bg-gray-900 text-gray-300 hover:border-purple-300'
                        }`}
                        aria-label={`${label}: ${value}`}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className="rounded-xl border border-gray-800 bg-gray-950/40 p-3">
          <h3 className="mb-3 text-sm font-semibold text-teal-300">Open Text</h3>
          <label className="block text-sm text-gray-300">
            What did you like most?
            <textarea
              value={likedMost}
              onChange={(event) => setLikedMost(event.target.value)}
              className="mt-2 min-h-20 w-full rounded-xl border border-gray-700 bg-gray-950 p-3 text-sm text-gray-100 outline-none focus:border-purple-300"
              placeholder="Optional"
            />
          </label>
          <label className="mt-3 block text-sm text-gray-300">
            What would you improve?
            <textarea
              value={improve}
              onChange={(event) => setImprove(event.target.value)}
              className="mt-2 min-h-20 w-full rounded-xl border border-gray-700 bg-gray-950 p-3 text-sm text-gray-100 outline-none focus:border-purple-300"
              placeholder="Optional"
            />
          </label>
        </section>
      </div>

      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}

      <button
        type="button"
        onClick={submitSurvey}
        disabled={!complete || submitting}
        className="mt-4 rounded-lg bg-purple-400 px-4 py-2 text-sm font-semibold text-gray-950 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Submitting...' : 'Submit Study Survey'}
      </button>
    </div>
  )
}
