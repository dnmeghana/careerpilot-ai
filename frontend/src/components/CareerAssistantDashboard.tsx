import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, getApiErrorMessage, type Interview, type Job } from '../lib/api'
import { Icon } from './Icon'

type Message = { id: number; role: 'user' | 'assistant'; text: string; contextLabels?: string[] }

const prompts = ['How can I improve my resume?', 'What skills am I missing for this job?', 'What should I prepare for this interview?', 'What roles match my skills?']

export function CareerAssistantDashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [jobId, setJobId] = useState('')
  const [interviewId, setInterviewId] = useState('')
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    Promise.all([api.get<Job[]>('/jobs'), api.get<Interview[]>('/interviews')])
      .then(([jobResponse, interviewResponse]) => {
        setJobs(jobResponse.data)
        setInterviews(interviewResponse.data)
        setJobId(jobResponse.data[0]?.id ?? '')
        setInterviewId(interviewResponse.data[0]?.id ?? '')
      })
      .catch(() => setError('We could not load your career context. You can still ask a general question.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function send(event?: FormEvent) {
    event?.preventDefault()
    const text = message.trim()
    if (!text || sending) return
    setMessage('')
    setError('')
    const userMessage: Message = { id: Date.now(), role: 'user', text }
    setMessages((current) => [...current, userMessage])
    setSending(true)
    try {
      const { data } = await api.post<{ response: string; context_labels: string[] }>('/assistant/chat', {
        message: text,
        job_id: jobId || undefined,
        interview_id: interviewId || undefined,
      })
      setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', text: data.response, contextLabels: data.context_labels }])
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'The assistant could not respond right now.'))
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="assistant-page">
      <div className="assistant-heading">
        <div><p className="page-kicker">Your career copilot</p><h1>AI Career Assistant</h1><p>Ask for a sharper next step, grounded in the work you have already saved.</p></div>
        <div className="assistant-status"><span /> Context stays private to your account</div>
      </div>
      <section className="assistant-shell">
        <aside className="assistant-context">
          <div className="assistant-context-icon"><Icon name="spark" /></div>
          <p className="page-kicker">Working context</p>
          <h2>Give the answer somewhere to land.</h2>
          <p>The assistant can use your active resume and the records you select here. It never receives another user's data.</p>
          <label>Focus job<select value={jobId} onChange={(event) => setJobId(event.target.value)} disabled={loading}><option value="">No job selected</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}</select></label>
          <label>Interview context<select value={interviewId} onChange={(event) => setInterviewId(event.target.value)} disabled={loading}><option value="">No interview selected</option>{interviews.map((interview) => <option key={interview.id} value={interview.id}>{interview.interview_type} · {interview.job_title}</option>)}</select></label>
          <div className="assistant-context-note"><strong>Private context</strong><span>Active resume · applications · skill gaps · interviews</span></div>
        </aside>
        <div className="assistant-chat">
          <div className="assistant-chat-header"><div><span className="assistant-avatar"><Icon name="spark" /></span><span><strong>CareerPilot</strong><small>Ready when you are</small></span></div><span className="assistant-live"><i /> Online</span></div>
          <div className="assistant-messages">
            {!messages.length && <div className="assistant-welcome"><span className="assistant-welcome-icon"><Icon name="chat" /></span><h2>What are you working through?</h2><p>Ask a question or choose a starting point. I will keep the advice practical and tied to your career data.</p><div className="assistant-prompts">{prompts.map((prompt) => <button key={prompt} onClick={() => setMessage(prompt)}>{prompt}</button>)}</div></div>}
            {messages.map((item) => <div className={`assistant-message ${item.role}`} key={item.id}><div className="assistant-bubble">{item.text}</div>{item.contextLabels?.length ? <div className="assistant-used-context">Using {item.contextLabels.join(' · ')}</div> : null}</div>)}
            {sending && <div className="assistant-message assistant"><div className="assistant-bubble assistant-typing"><i /><i /><i /></div></div>}
            <div ref={endRef} />
          </div>
          {error && <div className="assistant-error" role="alert">{error}</div>}
          <form className="assistant-composer" onSubmit={send}><textarea value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} rows={2} placeholder="Ask your career question..." aria-label="Ask the AI Career Assistant" /><button className="button" disabled={!message.trim() || sending} aria-label="Send message"><Icon name="arrow" /></button></form>
          <small className="assistant-disclaimer">AI guidance can be useful, but your judgment and review come first.</small>
        </div>
      </section>
    </main>
  )
}
