import { useEffect, useState } from 'react'
import { api, getApiErrorMessage, type Job, type MockInterview, type Resume } from '../lib/api'
import { Icon } from './Icon'

const scoreTone = (score: number | null) => score === null ? '' : score >= 75 ? 'strong' : score >= 60 ? 'steady' : 'needs-work'

export function MockInterviewDashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [resumes, setResumes] = useState<Resume[]>([])
  const [jobId, setJobId] = useState('')
  const [resumeId, setResumeId] = useState('')
  const [interviewType, setInterviewType] = useState('Behavioral')
  const [interview, setInterview] = useState<MockInterview | null>(null)
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [showFeedback, setShowFeedback] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get<Job[]>('/jobs'), api.get<Resume[]>('/resumes')])
      .then(([jobResponse, resumeResponse]) => {
        setJobs(jobResponse.data)
        setResumes(resumeResponse.data)
        setJobId(jobResponse.data[0]?.id ?? '')
        setResumeId(resumeResponse.data.find((item) => item.is_active)?.id ?? resumeResponse.data[0]?.id ?? '')
      })
      .catch(() => setError('We could not prepare your interview room.'))
      .finally(() => setLoading(false))
  }, [])

  const currentQuestion = interview && interview.current_question < interview.questions.length
    ? interview.questions[interview.current_question]
    : null
  const answeredCount = interview?.questions.filter((question) => question.answer.trim()).length ?? 0
  const finished = Boolean(interview?.completed_at)
  const currentEvaluation = showFeedback && interview ? interview.questions[interview.current_question - 1] : null

  async function start() {
    setStarting(true)
    setError('')
    try {
      const { data } = await api.post<MockInterview>('/mock-interviews', { job_id: jobId || undefined, resume_id: resumeId || undefined, interview_type: interviewType })
      setInterview(data)
      setAnswer('')
      setShowFeedback(false)
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Could not start the mock interview.'))
    } finally {
      setStarting(false)
    }
  }

  async function submitAnswer() {
    if (!interview || !currentQuestion || !answer.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const { data } = await api.post<MockInterview>(`/mock-interviews/${interview.id}/answers/${currentQuestion.id}`, { answer })
      setInterview(data)
      setAnswer('')
      setShowFeedback(true)
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Could not submit your answer.'))
    } finally {
      setSubmitting(false)
    }
  }

  function continueInterview() {
    setShowFeedback(false)
  }

  if (loading) return <main className="mock-page"><div className="resume-loading">Preparing your interview room...</div></main>

  if (!interview) return (
    <main className="mock-page">
      <div className="mock-heading"><div><p className="page-kicker">Live practice room</p><h1>Mock interview</h1><p>Take a breath. One question at a time, with useful feedback after every answer.</p></div></div>
      {error && <div className="resume-error" role="alert"><strong>Something went wrong</strong><span>{error}</span></div>}
      <section className="mock-lobby">
        <div className="mock-lobby-mark"><Icon name="mic" /></div>
        <div><p className="page-kicker">Before we begin</p><h2>Set the room for your next conversation.</h2><p>Your answers are evaluated privately and saved to your account so you can see patterns over time.</p></div>
        <div className="mock-setup-grid">
          <label>Role<select value={jobId} onChange={(event) => setJobId(event.target.value)}><option value="">General practice</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}</select></label>
          <label>Interview style<select value={interviewType} onChange={(event) => setInterviewType(event.target.value)}><option>Behavioral</option><option>Technical</option><option>HR</option><option>System Design</option></select></label>
          <label>Resume context<select value={resumeId} onChange={(event) => setResumeId(event.target.value)}><option value="">No resume context</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.filename}{resume.is_active ? ' · Active' : ''}</option>)}</select></label>
        </div>
        <button className="button mock-start-button" onClick={start} disabled={starting}><Icon name="play" /> {starting ? 'Opening room...' : 'Start mock interview'}</button>
      </section>
    </main>
  )

  if (finished) return (
    <main className="mock-page">
      <div className="mock-heading"><div><p className="page-kicker">Interview debrief</p><h1>That is a wrap.</h1><p>Here is the signal from this practice round. Keep the useful parts and try again when you are ready.</p></div><button className="button button-small" onClick={() => setInterview(null)}><Icon name="play" /> New interview</button></div>
      <section className="mock-final-score"><span>Overall score</span><strong>{Math.round(interview.overall_score ?? 0)}</strong><small>/ 100</small></section>
      <div className="mock-result-grid"><article><p className="page-kicker">Strong areas</p><h2>What came through</h2>{interview.strong_areas.length ? <ul>{interview.strong_areas.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mock-muted">Keep building specific examples to make your strengths easier to hear.</p>}</article><article><p className="page-kicker">Weak areas</p><h2>Where to focus</h2>{interview.weak_areas.length ? <ul>{interview.weak_areas.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mock-muted">No major weak area surfaced in this round.</p>}</article><article className="mock-recommendations"><p className="page-kicker">Recommendations</p><h2>Your next reps</h2>{interview.recommendations.length ? <ul>{interview.recommendations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="mock-muted">Review each answer and write one sharper version before your next round.</p>}</article></div>
      <section className="mock-answer-review"><div className="mock-section-heading"><h2>Answer review</h2><span>{answeredCount} responses</span></div>{interview.questions.map((question, index) => <article key={question.id}><div><span className="question-number">Q{index + 1}</span><strong>{question.question}</strong></div><b className={scoreTone(question.score)}>{Math.round(question.score ?? 0)}</b></article>)}</section>
    </main>
  )

  return (
    <main className="mock-page">
      <div className="mock-session-top"><div><p className="page-kicker">{interview.company ?? 'Practice room'}</p><h1>{interview.job_title ?? 'Mock interview'}</h1><span>{interview.interview_type} · Question {Math.min(interview.current_question + 1, interview.questions.length)} of {interview.questions.length}</span></div><button className="text-button" onClick={() => setInterview(null)}>Leave interview</button></div>
      <div className="mock-progress" aria-label={`${answeredCount} of ${interview.questions.length} questions answered`}><i style={{ width: `${(answeredCount / interview.questions.length) * 100}%` }} /></div>
      {error && <div className="resume-error" role="alert"><strong>Something went wrong</strong><span>{error}</span></div>}
      {currentEvaluation ? <section className="mock-feedback-stage"><div className="mock-feedback-intro"><span className="mock-eyebrow"><Icon name="check" /> Answer recorded</span><h2>Here is how that answer landed.</h2><div className={`mock-score ${scoreTone(currentEvaluation.score)}`}><strong>{Math.round(currentEvaluation.score ?? 0)}</strong><span>/ 100</span></div></div><div className="mock-feedback-grid"><article><h3>Strengths</h3><ul>{currentEvaluation.feedback?.strengths?.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Weaknesses</h3><ul>{currentEvaluation.feedback?.weaknesses?.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Specific improvements</h3><ul>{currentEvaluation.feedback?.suggestions?.map((item) => <li key={item}>{item}</li>)}</ul></article></div><button className="button" onClick={continueInterview}>Continue to next question <Icon name="arrow" /></button></section> : currentQuestion ? <section className="mock-question-stage"><div className="mock-question-meta"><span>Question {interview.current_question + 1}</span><span>{currentQuestion.category} · {currentQuestion.difficulty}</span></div><h2>{currentQuestion.question}</h2><p>Take a moment to think, then answer as if you were speaking to the interviewer.</p><textarea autoFocus rows={9} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Your answer..." /><div className="mock-answer-actions"><span>{answer.trim().length} characters</span><button className="button" onClick={submitAnswer} disabled={!answer.trim() || submitting}>{submitting ? 'Evaluating...' : 'Submit answer'} <Icon name="arrow" /></button></div></section> : null}
    </main>
  )
}
