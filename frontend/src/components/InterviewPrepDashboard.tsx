import { useEffect, useState, type FormEvent } from 'react'
import { api, getApiErrorMessage, interviewTypes, type Interview, type InterviewType, type Job, type Resume } from '../lib/api'
import { ListControls, Pagination } from './ListControls'
import { Icon } from './Icon'
import { pageItems } from './pagination'

const difficultyColors = {
  Easy: '#277c5b',
  Medium: '#f6d77a',
  Hard: '#e96856',
}

export function InterviewPrepDashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [resumes, setResumes] = useState<Resume[]>([])
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('recent')
  const [page, setPage] = useState(1)
  const [jobId, setJobId] = useState('')
  const [resumeId, setResumeId] = useState('')
  const [type, setType] = useState<InterviewType>('HR')
  const [selected, setSelected] = useState<Interview | null>(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const filteredInterviews = interviews.filter((item) => `${item.job_title} ${item.company} ${item.interview_type}`.toLowerCase().includes(query.toLowerCase()) && (filter === 'all' || item.interview_type === filter)).sort((a, b) => sort === 'type' ? a.interview_type.localeCompare(b.interview_type) : sort === 'company' ? a.company.localeCompare(b.company) : b.created_at.localeCompare(a.created_at))
  const visibleInterviews = pageItems(filteredInterviews, page)

  useEffect(() => {
    Promise.all([api.get<Job[]>('/jobs'), api.get<Interview[]>('/interviews'), api.get<Resume[]>('/resumes')])
      .then(([jobResponse, interviewResponse, resumeResponse]) => {
        setJobs(jobResponse.data)
        setInterviews(interviewResponse.data)
        setResumes(resumeResponse.data)
        setJobId(jobResponse.data[0]?.id ?? '')
        setResumeId(resumeResponse.data.find((resume) => resume.is_active)?.id ?? resumeResponse.data[0]?.id ?? '')
        setSelected(interviewResponse.data[0] ?? null)
        setNotes(interviewResponse.data[0]?.notes ?? '')
      })
      .catch(() => setError('We could not load your interview preparation.'))
      .finally(() => setLoading(false))
  }, [])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const { data } = await api.post<Interview>('/interviews', { job_id: jobId, interview_type: type, resume_id: resumeId || undefined })
      setInterviews((current) => [data, ...current])
      setSelected(data)
      setNotes(data.notes ?? '')
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Could not create interview preparation.'))
    } finally {
      setSaving(false)
    }
  }

  async function regenerate() {
    if (!selected) return
    setSaving(true)
    setError('')
    try {
      const { data } = await api.post<Interview>(`/interviews/${selected.id}/regenerate`, { resume_id: resumeId || undefined })
      setSelected(data)
      setInterviews((current) => current.map((item) => (item.id === data.id ? data : item)))
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Could not regenerate questions.'))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(question: Interview['questions'][number]) {
    if (!selected) return
    try {
      const { data } = await api.patch<Interview>(`/interviews/${selected.id}`, {
        question_id: question.id,
        completed: !question.completed,
      })
      setSelected(data)
      setInterviews((current) => current.map((item) => (item.id === data.id ? data : item)))
    } catch {
      setError('Could not update question progress.')
    }
  }

  async function saveNotes() {
    if (!selected) return
    try {
      const { data } = await api.patch<Interview>(`/interviews/${selected.id}`, { notes })
      setSelected(data)
      setInterviews((current) => current.map((item) => (item.id === data.id ? data : item)))
    } catch {
      setError('Could not save your notes.')
    }
  }

  if (loading) {
    return (
      <main className="interview-page">
        <div className="resume-loading">Loading your interview preparation...</div>
      </main>
    )
  }

  return (
    <main className="interview-page">
      <div className="interview-heading">
        <div>
          <p className="page-kicker">Local preparation studio</p>
          <h1>Interview prep</h1>
          <p>Choose a role, pick a conversation style, and practice with focused prompts.</p>
        </div>
      </div>

      {error && (
        <div className="resume-error" role="alert">
          <strong>Something went wrong</strong>
          <span>{error}</span>
        </div>
      )}

      <section className="interview-create">
        <form onSubmit={create}>
          <label>
            Job
            <select required value={jobId} onChange={(event) => setJobId(event.target.value)}>
              <option value="">Choose a saved job</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title} · {job.company}
                </option>
              ))}
            </select>
          </label>
          <label>
            Interview type
            <select value={type} onChange={(event) => setType(event.target.value as InterviewType)}>
              {interviewTypes.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Resume context
            <select value={resumeId} onChange={(event) => setResumeId(event.target.value)}>
              <option value="">No resume selected</option>
              {resumes.map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.filename}{resume.is_active ? ' · Active' : ''}
                </option>
              ))}
            </select>
          </label>
          <button className="button" disabled={!jobs.length || saving}>
            <Icon name="book" /> {saving ? 'Generating...' : 'Create interview'}
          </button>
        </form>
        {!jobs.length && <p className="analysis-muted">Add a saved job before generating questions.</p>}
      </section>

      {interviews.length > 0 && (
        <div className="interview-layout">
          <aside className="interview-list">
            <div className="interview-list-heading">
              <h2>Saved sessions</h2>
              <span>{interviews.length}</span>
            </div>
            <ListControls search={query} onSearch={(value) => { setQuery(value); setPage(1) }} placeholder="Search sessions" filter={<select aria-label="Filter interview type" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1) }}><option value="all">All types</option>{interviewTypes.map((item) => <option key={item}>{item}</option>)}</select>} sort={<select aria-label="Sort interviews" value={sort} onChange={(event) => { setSort(event.target.value); setPage(1) }}><option value="recent">Recently added</option><option value="type">Interview type</option><option value="company">Company</option></select>} />
            {visibleInterviews.items.map((item) => (
              <button
                key={item.id}
                className={`interview-session ${selected?.id === item.id ? 'active' : ''}`}
                onClick={() => {
                  setSelected(item)
                  setNotes(item.notes ?? '')
                }}
              >
                <strong>{item.interview_type}</strong>
                <span>{item.job_title}</span>
                <small>
                  {item.company} · {item.questions.filter((question) => question.completed).length}/{item.questions.length} complete
                </small>
              </button>
            ))}
            <Pagination page={page} pageCount={visibleInterviews.pageCount} onPageChange={setPage} />
          </aside>

          {selected && (
            <section className="interview-content">
              <div className="interview-content-heading">
                <div>
                  <p className="page-kicker">{selected.company}</p>
                  <h2>{selected.job_title}</h2>
                  <span>
                    {selected.interview_type} · {selected.questions.filter((q) => q.completed).length}/{selected.questions.length} complete
                  </span>
                </div>
                <button className="button button-small" onClick={regenerate} disabled={saving}>
                  <Icon name="refresh" /> {saving ? 'Generating...' : 'Regenerate questions'}
                </button>
              </div>

              <div className="question-list">
                {selected.questions.map((question, index) => (
                  <article className="question-card" key={question.id}>
                    <div className="question-checkbox">
                      <input
                        type="checkbox"
                        checked={question.completed}
                        onChange={() => toggle(question)}
                        aria-label={`Mark question ${index + 1} as complete`}
                      />
                    </div>
                    <div className="question-content">
                      <div className="question-header">
                        <span className="question-number">Q{index + 1}</span>
                        <span className="question-category">{question.category}</span>
                        {question.difficulty && (
                          <span
                            className="question-difficulty"
                            style={{ color: difficultyColors[question.difficulty as keyof typeof difficultyColors] }}
                          >
                            {question.difficulty}
                          </span>
                        )}
                      </div>
                      <p className="question-text">{question.question}</p>
                      {question.suggested_answer && (
                        <details className="question-answer">
                          <summary>Suggested answer points</summary>
                          <p>{question.suggested_answer}</p>
                        </details>
                      )}
                    </div>
                  </article>
                ))}
              </div>

              <section className="interview-notes">
                <h3>Your notes</h3>
                <label>
                  <textarea
                    rows={4}
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Add notes, reflection, or areas to improve..."
                  />
                </label>
                <button onClick={saveNotes} className="button button-small">
                  Save notes
                </button>
              </section>
            </section>
          )}
        </div>
      )}
    </main>
  )
}
