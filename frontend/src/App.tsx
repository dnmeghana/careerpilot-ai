import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, applicationStatuses, getApiErrorMessage, MAX_RESUME_SIZE_BYTES, uploadResume, analyzeResumeVsJob, forgotPassword, resetPassword, type Application, type ApplicationInput, type ApplicationStatus, type Job, type JobInput, type Resume, type ResumeJobAnalysis } from './lib/api'
import { useAuth } from './lib/useAuth'
import { Icon } from './components/Icon'
import { AnalysisRequestSelector } from './components/AnalysisRequestSelector'
import { AnalysisResultsCard } from './components/AnalysisResultsCard'
import { SkillGapDashboard } from './components/SkillGapDashboard'
import { InterviewPrepDashboard } from './components/InterviewPrepDashboard'
import { MockInterviewDashboard } from './components/MockInterviewDashboard'
import { CareerAssistantDashboard } from './components/CareerAssistantDashboard'
import { AutomationDashboard } from './components/AutomationDashboard'
import { ListControls } from './components/ListControls'
import './App.css'

const navItems = [
  { label: 'Dashboard', to: '/dashboard', icon: 'grid' },
  { label: 'Resumes', to: '/resumes', icon: 'file' },
  { label: 'Jobs', to: '/jobs', icon: 'briefcase' },
  { label: 'Applications', to: '/applications', icon: 'send' },
  { label: 'Automation', to: '/automation', icon: 'play' },
  { label: 'Resume Analysis', to: '/analysis', icon: 'spark' },
  { label: 'Skill Gap', to: '/skill-gap', icon: 'spark' },
  { label: 'Interview Prep', to: '/interview-prep', icon: 'book' },
  { label: 'Mock Interview', to: '/mock-interview', icon: 'mic' },
  { label: 'AI Career Assistant', to: '/assistant', icon: 'chat' },
  { label: 'Analytics', to: '/analytics', icon: 'chart' },
] as const

type DashboardData = {
  stats: { total_applications: number; interviews: number; offers: number; rejections: number; success_rate: number }
  recent_applications: { id: string; company: string; role: string; status: string; updated_at: string }[]
  upcoming_interviews: { id: string; company: string; role: string; type: string; scheduled_at: string }[]
  skill_gaps: { id: string; skill: string; role: string; company: string; priority: number }[]
  activity: { date: string; status: string; company: string }[]
}

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [profileOpen, setProfileOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  if (!user) return <div className="app-shell"><header className="marketing-topbar"><Link className="brand" to="/"><span className="brand-mark">CP</span><span>CareerPilot</span></Link><div className="topbar-actions"><Link className="text-link" to="/login">Log in</Link><Link className="button button-small" to="/register">Get started</Link></div></header>{children}</div>
  return <div className="workspace-shell"><aside className={`sidebar ${menuOpen ? 'mobile-open' : ''}`}><Link className="brand" to="/dashboard"><span className="brand-mark">CP</span><span>CareerPilot</span></Link><p className="sidebar-label">Workspace</p><nav className="sidebar-nav" aria-label="Workspace navigation">{navItems.map((item) => <NavLink key={item.to} to={item.to} onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? 'active' : ''}><Icon name={item.icon} />{item.label}</NavLink>)}</nav><div className="sidebar-footer"><div className="pilot-note"><span className="note-icon"><Icon name="spark" /></span><strong>Make your next move count.</strong><span>Keep momentum on your side.</span></div><button className="sidebar-user" onClick={() => setProfileOpen(!profileOpen)}><span className="avatar">{user.name.charAt(0).toUpperCase()}</span><span><strong>{user.name}</strong><small>Personal account</small></span><Icon name="chevron" /></button>{profileOpen && <div className="profile-menu"><span>{user.email}</span><button onClick={logout}>Log out</button></div>}</div></aside><div className="workspace-main"><header className="workspace-topbar"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(!menuOpen)}><Icon name="grid" /></button><div className="breadcrumbs">Workspace <span>/</span> <strong>{navItems.find((item) => item.to === location.pathname)?.label ?? 'Dashboard'}</strong></div><div className="topbar-actions"><button className="icon-button" aria-label="Notifications"><span className="notification-dot" /><span className="bell">&#9673;</span></button><div className="top-avatar">{user.name.charAt(0).toUpperCase()}</div></div></header>{children}</div></div>
}

function LandingPage() {
  return <main className="landing"><section className="hero-section"><div className="eyebrow"><span className="status-dot" /> Your next move, mapped</div><h1>A calmer way to <em>move forward</em> in your career.</h1><p className="hero-copy">CareerPilot brings your resumes, applications, and interview prep into one focused workspace, so every opportunity gets your best thinking.</p><div className="hero-actions"><Link className="button" to="/register">Build your workspace <span aria-hidden="true">-&gt;</span></Link><Link className="text-link" to="/login">I already have an account</Link></div><div className="hero-note"><span>01</span> Designed for the full job search, not just the next application.</div></section><section className="feature-strip" aria-label="CareerPilot features"><article><span className="feature-number">01</span><h2>See the signal</h2><p>Keep every application and next step visible in one clear view.</p></article><article><span className="feature-number">02</span><h2>Close the gaps</h2><p>Compare your strengths to the roles you actually want.</p></article><article><span className="feature-number">03</span><h2>Show up ready</h2><p>Turn preparation into a repeatable habit before interview day.</p></article></section></main>
}

function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return <main className="placeholder-page"><div className="eyebrow"><span className="status-dot" /> Workspace module</div><h1>{title}</h1><p>{description}</p><span className="coming-soon">Ready for your data</span></main>
}

function SkillGapPage() {
  return <SkillGapDashboard />
}

function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('recent')
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  useEffect(() => { api.get<Resume[]>('/resumes').then(({ data }) => setResumes(data)).catch(() => setError('We could not load your resumes. Please try again.')).finally(() => setLoading(false)) }, [])
  async function handleFile(file?: File) {
    if (!file || uploading) return
    setError('')
    if (file.type !== 'application/pdf' || !file.name.toLowerCase().endsWith('.pdf')) { setError('Only PDF files can be uploaded.'); return }
    if (file.size > MAX_RESUME_SIZE_BYTES) { setError('Your resume must be 10 MB or smaller.'); return }
    setUploading(true); setProgress(0)
    try { const resume = await uploadResume(file, setProgress); setResumes((current) => [resume, ...current.map((item) => ({ ...item, is_active: false }))]) } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, 'Upload failed. Please try again.')) } finally { setUploading(false) }
  }
  async function setActive(id: string) { try { const { data } = await api.put<Resume>(`/resumes/${id}/active`); setResumes((current) => current.map((item) => ({ ...item, is_active: item.id === data.id }))) } catch { setError('Could not change the active resume.') } }
  async function remove(id: string) { try { await api.delete(`/resumes/${id}`); setResumes((current) => current.filter((item) => item.id !== id)) } catch { setError('Could not delete this resume.') } }
  const date = (value: string) => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
  const filteredResumes = resumes.filter((resume) => resume.filename.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'name' ? a.filename.localeCompare(b.filename) : b.updated_at.localeCompare(a.updated_at))
  return <main className="resume-page"><div className="resume-heading"><div><p className="page-kicker">Your documents</p><h1>Resumes</h1><p>Keep a focused, current version ready for every opportunity.</p></div><button className="button button-small" onClick={() => fileInput.current?.click()}><Icon name="file" /> Upload resume</button></div><input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => handleFile(event.target.files?.[0])} /><section className={`upload-zone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); handleFile(event.dataTransfer.files[0]) }} onClick={() => !uploading && fileInput.current?.click()}><div className="upload-symbol"><Icon name="file" /></div><strong>{uploading ? `Uploading resume... ${progress}%` : 'Drop your PDF here, or browse'}</strong><span>{uploading ? 'Extracting text and saving your resume' : 'PDF only · Maximum file size 10 MB'}</span>{uploading && <div className="upload-progress"><i style={{ width: `${progress}%` }} /></div>}</section>{error && <div className="resume-error" role="alert"><strong>Something went wrong</strong><span>{error}</span></div>}<div className="resume-list-heading"><h2>Saved resumes <span>{resumes.length}</span></h2><ListControls search={query} onSearch={setQuery} placeholder="Search filename" sort={<select aria-label="Sort resumes" value={sort} onChange={(event) => setSort(event.target.value)}><option value="recent">Recently updated</option><option value="name">Filename</option></select>} /></div>{loading ? <div className="resume-loading">Loading your resumes...</div> : filteredResumes.length === 0 ? <div className="resume-empty"><div className="empty-icon"><Icon name="file" /></div><h2>{resumes.length ? 'No resumes match your search' : 'Your resume library is empty'}</h2><p>{resumes.length ? 'Try a different filename.' : 'Upload a PDF to extract its text and make it available across your workspace.'}</p><button className="button button-small" onClick={() => fileInput.current?.click()}>Upload {resumes.length ? 'a resume' : 'your first resume'} <Icon name="arrow" /></button></div> : <div className="resume-list">{filteredResumes.map((resume) => <article className={`resume-card ${resume.is_active ? 'active' : ''}`} key={resume.id}><div className="resume-file-icon"><Icon name="file" /></div><div className="resume-card-main"><div className="resume-card-title"><h3>{resume.filename}</h3>{resume.is_active && <span className="active-badge">Active resume</span>}</div><span className="resume-date">Uploaded {date(resume.created_at)}</span><p>{resume.extracted_text_preview || 'No selectable text was found in this PDF.'}</p></div><div className="resume-actions">{!resume.is_active && <button className="text-button" onClick={() => setActive(resume.id)}>Set active</button>}<button className="delete-button" aria-label={`Delete ${resume.filename}`} onClick={() => remove(resume.id)}>Delete</button></div></article>)}</div>}</main>
}

function JobForm({ job, onSaved }: { job?: Job; onSaved: (saved: Job) => void }) {
  const navigate = useNavigate()
  const [form, setForm] = useState<JobInput>({ title: job?.title ?? '', company: job?.company ?? '', description: job?.description ?? '', url: job?.url ?? '', location: job?.location ?? '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.title.trim() || !form.company.trim()) { setError('Job title and company are required.'); return }
    setError(''); setSubmitting(true)
    try {
      const { data } = job ? await api.put<Job>(`/jobs/${job.id}`, form) : await api.post<Job>('/jobs', form)
      onSaved(data)
      if (!job) navigate(`/jobs/${data.id}`)
    } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, 'Could not save this job.')) } finally { setSubmitting(false) }
  }
  return <form className="job-form" onSubmit={submit}><div className="job-form-grid"><label>Job title<input required maxLength={255} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Senior Product Designer" /></label><label>Company<input required maxLength={255} value={form.company} onChange={(event) => setForm({ ...form, company: event.target.value })} placeholder="Northstar Labs" /></label><label>Location<input maxLength={255} value={form.location ?? ''} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Remote or city" /></label><label>Job URL<input type="url" maxLength={2048} value={form.url ?? ''} onChange={(event) => setForm({ ...form, url: event.target.value })} placeholder="https://company.com/jobs/..." /></label></div><label>Job description<textarea rows={7} value={form.description ?? ''} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="What would you be working on?" /></label>{error && <p className="form-error" role="alert">{error}</p>}<div className="job-form-actions"><button className="button" type="submit" disabled={submitting}>{submitting ? 'Saving...' : job ? 'Save changes' : 'Create job'} <Icon name="arrow" /></button>{job && <Link className="text-link" to={`/jobs/${job.id}`}>Cancel</Link>}</div></form>
}

function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('recent')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.get<Job[]>('/jobs').then(({ data }) => setJobs(data)).catch(() => setError('We could not load your jobs. Please try again.')).finally(() => setLoading(false)) }, [])
  const filtered = jobs.filter((job) => `${job.title} ${job.company} ${job.location ?? ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'title' ? a.title.localeCompare(b.title) : sort === 'company' ? a.company.localeCompare(b.company) : b.created_at.localeCompare(a.created_at))
  async function remove(id: string) { if (!window.confirm('Delete this job?')) return; try { await api.delete(`/jobs/${id}`); setJobs((current) => current.filter((job) => job.id !== id)) } catch { setError('Could not delete this job.') } }
    return <main className="jobs-page"><div className="jobs-heading"><div><p className="page-kicker">Your opportunities</p><h1>Jobs</h1><p>Keep promising roles close and your next move visible.</p></div><button className="button button-small" onClick={() => setShowForm(!showForm)}><Icon name="briefcase" /> {showForm ? 'Close form' : 'Add job'}</button></div>{showForm && <section className="job-editor"><p className="page-kicker">New opportunity</p><h2>Add a job</h2><JobForm onSaved={(job) => { setJobs((current) => [job, ...current]); setShowForm(false) }} /></section>}{error && <div className="resume-error" role="alert"><strong>Something went wrong</strong><span>{error}</span></div>}<div className="job-toolbar"><h2>Saved jobs <span>{jobs.length}</span></h2><ListControls search={query} onSearch={setQuery} placeholder="Search title, company, location" sort={<select aria-label="Sort jobs" value={sort} onChange={(event) => setSort(event.target.value)}><option value="recent">Recently added</option><option value="title">Title</option><option value="company">Company</option></select>} /></div>{loading ? <div className="resume-loading">Loading your jobs...</div> : filtered.length === 0 ? <div className="job-empty"><div className="empty-icon"><Icon name="briefcase" /></div><h2>{jobs.length ? 'No jobs match your search' : 'Your job board is empty'}</h2><p>{jobs.length ? 'Try a different title, company, or location.' : 'Add the roles you are considering to keep your search organized.'}</p>{!jobs.length && <button className="button button-small" onClick={() => setShowForm(true)}>Add your first job <Icon name="arrow" /></button>}</div> : <div className="job-list">{filtered.map((job) => <article className="job-card" key={job.id}><div className="company-avatar">{job.company.charAt(0).toUpperCase()}</div><div className="job-card-main"><Link to={`/jobs/${job.id}`}><h3>{job.title}</h3></Link><p>{job.company}{job.location && <> <span>·</span> {job.location}</>}</p><small>Added {new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(job.created_at))}</small></div><div className="job-card-actions"><Link className="text-link" to={`/jobs/${job.id}`}>View</Link><button className="text-button danger" onClick={() => remove(job.id)}>Delete</button></div></article>)}</div>}</main>
}

function JobDetailsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { if (id) api.get<Job>(`/jobs/${id}`).then(({ data }) => setJob(data)).catch(() => setError('This job could not be found.')) }, [id])
  async function remove() { if (!job || !window.confirm('Delete this job?')) return; try { await api.delete(`/jobs/${job.id}`); navigate('/jobs') } catch { setError('Could not delete this job.') } }
  if (error) return <main className="placeholder-page"><p className="form-error" role="alert">{error}</p><Link className="text-link" to="/jobs">Back to jobs</Link></main>
  if (!job) return <main className="loading-page">Loading job...</main>
  return <main className="job-detail-page"><Link className="back-link" to="/jobs">&lt;- All jobs</Link>{editing ? <section className="job-editor"><p className="page-kicker">Edit opportunity</p><h1>Edit job</h1><JobForm job={job} onSaved={(saved) => { setJob(saved); setEditing(false) }} /></section> : <><div className="job-detail-heading"><div><p className="page-kicker">{job.company}</p><h1>{job.title}</h1><p>{job.location || 'Location not specified'}</p></div><div className="job-form-actions"><button className="button button-small" onClick={() => setEditing(true)}>Edit job</button><button className="text-button danger" onClick={remove}>Delete</button></div></div><section className="job-description"><h2>Job description</h2><p>{job.description || 'No description added yet.'}</p>{job.url && <a className="text-link" href={job.url} target="_blank" rel="noreferrer">Open job posting <Icon name="arrow" /></a>}</section></>}</main>
}

const statusLabel = (status: string) => status.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

function ApplicationForm({ application, jobs, onSaved, onCancel }: { application?: Application; jobs: Job[]; onSaved: (item: Application) => void; onCancel: () => void }) {
  const [form, setForm] = useState<ApplicationInput>({ job_id: application?.job_id ?? jobs[0]?.id ?? '', status: application?.status ?? 'wishlist', application_date: application?.application_date ?? '', interview_date: application?.interview_date?.slice(0, 16) ?? '', salary: application?.salary ?? null, recruiter_name: application?.recruiter_name ?? '', recruiter_email: application?.recruiter_email ?? '', notes: application?.notes ?? '' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const update = (field: keyof ApplicationInput, value: string | number | null) => setForm((current) => ({ ...current, [field]: value }))
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); const payload = { ...form, application_date: form.application_date || null, interview_date: form.interview_date || null, recruiter_name: form.recruiter_name || null, recruiter_email: form.recruiter_email || null, notes: form.notes || null }; try { const { data } = application ? await api.put<Application>(`/applications/${application.id}`, payload) : await api.post<Application>('/applications', payload); onSaved(data) } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, 'Could not save this application.')) } finally { setSaving(false) } }
  return <form className="application-form" onSubmit={submit}><div className="application-form-grid"><label>Job<select required value={form.job_id} onChange={(event) => update('job_id', event.target.value)}><option value="">Select a saved job</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}</select></label><label>Status<select value={form.status} onChange={(event) => update('status', event.target.value as ApplicationStatus)}>{applicationStatuses.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select></label><label>Application date<input type="date" value={form.application_date} onChange={(event) => update('application_date', event.target.value)} /></label><label>Interview date<input type="datetime-local" value={form.interview_date} onChange={(event) => update('interview_date', event.target.value)} /></label><label>Salary<input type="number" min="0" step="0.01" value={form.salary ?? ''} onChange={(event) => update('salary', event.target.value ? Number(event.target.value) : null)} placeholder="120000" /></label><label>Recruiter name<input value={form.recruiter_name} onChange={(event) => update('recruiter_name', event.target.value)} placeholder="Alex Morgan" /></label><label>Recruiter email<input type="email" value={form.recruiter_email} onChange={(event) => update('recruiter_email', event.target.value)} placeholder="alex@company.com" /></label></div><label>Notes<textarea rows={4} value={form.notes} onChange={(event) => update('notes', event.target.value)} placeholder="Next steps, context, and follow-ups" /></label>{error && <p className="form-error" role="alert">{error}</p>}<div className="job-form-actions"><button className="button" disabled={saving}>{saving ? 'Saving...' : application ? 'Save changes' : 'Add application'} <Icon name="arrow" /></button><button type="button" className="text-button" onClick={onCancel}>Cancel</button></div></form>
}

function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]); const [jobs, setJobs] = useState<Job[]>([]); const [query, setQuery] = useState(''); const [filter, setFilter] = useState('all'); const [sort, setSort] = useState('updated'); const [view, setView] = useState<'table' | 'kanban'>('table'); const [editing, setEditing] = useState<Application | null | undefined>(undefined); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  useEffect(() => { Promise.all([api.get<Application[]>('/applications'), api.get<Job[]>('/jobs')]).then(([applicationResponse, jobResponse]) => { setApplications(applicationResponse.data); setJobs(jobResponse.data) }).catch(() => setError('We could not load your application tracker. Please try again.')).finally(() => setLoading(false)) }, [])
  useEffect(() => { const timer = window.setTimeout(() => { if (!loading) api.get<Application[]>('/applications', { params: { search: query || undefined, status: filter === 'all' ? undefined : filter, sort } }).then(({ data }) => setApplications(data)).catch(() => setError('Could not refresh the application list.')) }, 180); return () => window.clearTimeout(timer) }, [query, filter, sort, loading])
  function saved(item: Application) { setApplications((current) => current.some((entry) => entry.id === item.id) ? current.map((entry) => entry.id === item.id ? item : entry) : [item, ...current]); setEditing(undefined) }
  async function remove(id: string) { if (!window.confirm('Delete this application?')) return; try { await api.delete(`/applications/${id}`); setApplications((current) => current.filter((item) => item.id !== id)) } catch { setError('Could not delete this application.') } }
  async function move(item: Application, nextStatus: ApplicationStatus) { if (item.status === nextStatus) return; try { const { data } = await api.put<Application>(`/applications/${item.id}`, { ...item, status: nextStatus }); setApplications((current) => current.map((entry) => entry.id === item.id ? data : entry)) } catch { setError('Could not update the application status.') } }
  return <main className="applications-page"><div className="applications-heading"><div><p className="page-kicker">Your pipeline</p><h1>Applications</h1><p>Keep every opportunity moving with a clear next step.</p></div><button className="button button-small" onClick={() => setEditing(null)}><Icon name="send" /> Add application</button></div>{editing !== undefined && <section className="job-editor"><p className="page-kicker">{editing ? 'Update opportunity' : 'New opportunity'}</p><h2>{editing ? 'Edit application' : 'Track an application'}</h2>{jobs.length ? <ApplicationForm application={editing ?? undefined} jobs={jobs} onSaved={saved} onCancel={() => setEditing(undefined)} /> : <p className="form-error">Add a saved job before tracking an application.</p>}</section>}{error && <div className="resume-error" role="alert"><strong>Something went wrong</strong><span>{error}</span></div>}<div className="application-toolbar"><input aria-label="Search applications" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search roles, companies, notes" /><select aria-label="Filter by status" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All statuses</option>{applicationStatuses.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select><select aria-label="Sort applications" value={sort} onChange={(event) => setSort(event.target.value)}><option value="updated">Recently updated</option><option value="application_date">Application date</option><option value="salary">Salary</option><option value="company">Company</option></select><div className="view-toggle"><button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')}>Table</button><button className={view === 'kanban' ? 'active' : ''} onClick={() => setView('kanban')}>Board</button></div></div>{loading ? <div className="resume-loading">Loading your applications...</div> : !applications.length ? <div className="job-empty"><div className="empty-icon"><Icon name="send" /></div><h2>Your pipeline is waiting</h2><p>Track your first application and keep the next step close.</p><button className="button button-small" onClick={() => setEditing(null)}>Add your first application <Icon name="arrow" /></button></div> : view === 'table' ? <div className="application-table"><div className="application-row application-header"><span>Role</span><span>Status</span><span>Dates</span><span>Recruiter</span><span>Actions</span></div>{applications.map((item) => <div className="application-row" key={item.id}><div><strong>{item.title}</strong><small>{item.company}{item.location ? ` · ${item.location}` : ''}</small></div><select aria-label={`Status for ${item.title}`} value={item.status} onChange={(event) => move(item, event.target.value as ApplicationStatus)}>{applicationStatuses.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select><div><small>{item.application_date ? `Applied ${item.application_date}` : 'No application date'}</small><small>{item.interview_date ? `Interview ${new Date(item.interview_date).toLocaleDateString()}` : ''}</small></div><small>{item.recruiter_name || 'No recruiter added'}</small><div className="job-card-actions"><button className="text-button" onClick={() => setEditing(item)}>Edit</button><button className="text-button danger" onClick={() => remove(item.id)}>Delete</button></div></div>)}</div> : <div className="kanban-board">{applicationStatuses.map((status) => <section className="kanban-column" key={status} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { const item = applications.find((entry) => entry.id === event.dataTransfer.getData('application-id')); if (item) move(item, status) }}><div className="kanban-heading"><h2>{statusLabel(status)}</h2><span>{applications.filter((item) => item.status === status).length}</span></div>{applications.filter((item) => item.status === status).map((item) => <article className="kanban-card" draggable key={item.id} onDragStart={(event) => event.dataTransfer.setData('application-id', item.id)}><strong>{item.title}</strong><p>{item.company}</p>{item.salary && <small>${item.salary.toLocaleString()}</small>}<div><button className="text-button" onClick={() => setEditing(item)}>Edit</button><button className="text-button danger" onClick={() => remove(item.id)}>Delete</button></div></article>)}</section>)}</div>}</main>
}

function AnalysisPage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<ResumeJobAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get<Resume[]>('/resumes'), api.get<Job[]>('/jobs')])
      .then(([resumeResponse, jobResponse]) => {
        setResumes(resumeResponse.data)
        setJobs(jobResponse.data)
        const activeResume = resumeResponse.data.find((item) => item.is_active)
        setSelectedResumeId(activeResume?.id ?? resumeResponse.data[0]?.id ?? null)
        setSelectedJobId(jobResponse.data[0]?.id ?? null)
      })
      .catch(() => setError('We could not load your resumes and jobs.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleAnalyze() {
    if (!selectedResumeId || !selectedJobId) return
    setAnalyzing(true)
    setError('')
    try {
      const data = await analyzeResumeVsJob(selectedResumeId, selectedJobId)
      setAnalysis(data)
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Could not analyze these documents.'))
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <main className="analysis-page">
      <div className="analysis-heading">
        <div>
          <p className="page-kicker">Local analysis engine</p>
          <h1>Resume fit</h1>
          <p>Compare your resume with a role and find the clearest improvements.</p>
        </div>
      </div>

      <section className="analysis-selector-wrapper">
        <AnalysisRequestSelector
          resumes={resumes}
          jobs={jobs}
          selectedResumeId={selectedResumeId}
          selectedJobId={selectedJobId}
          isLoading={analyzing}
          onResumeSelect={setSelectedResumeId}
          onJobSelect={setSelectedJobId}
          onAnalyze={handleAnalyze}
          disabled={loading || resumes.length === 0 || jobs.length === 0}
        />
      </section>

      {error && (
        <div className="error-message" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <section className="analysis-results-wrapper">
        <AnalysisResultsCard analysis={analysis} isLoading={analyzing} />
      </section>
    </main>
  )
}

function InterviewPrepPage() {
  return <InterviewPrepDashboard />
}

function MockInterviewPage() {
  return <MockInterviewDashboard />
}

function AssistantPage() {
  return <CareerAssistantDashboard />
}

function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { api.get<DashboardData>('/dashboard').then(({ data: response }) => setData(response)).catch(() => setError('We could not load your dashboard. Check that the API is running, then try again.')).finally(() => setLoading(false)) }, [])
  const formatDate = (value: string | Date) => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(value))
  const formatTime = (value: string) => new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(value))
  const hasData = data && (data.stats.total_applications > 0 || data.upcoming_interviews.length > 0 || data.skill_gaps.length > 0)
    return <main className="dashboard-page"><div className="dashboard-heading"><div><p className="page-kicker">{formatDate(new Date())}</p><h1>Good morning, {user?.name.split(' ')[0]}.</h1><p>Here is the latest read on your career momentum.</p></div><button className="button button-small" onClick={() => window.location.reload()}><Icon name="refresh" /> Refresh data</button></div>{loading && <div className="dashboard-loading" aria-label="Loading dashboard"><div className="loading-bar" /><div className="loading-grid">{[1, 2, 3, 4, 5].map((item) => <div className="skeleton" key={item} />)}</div></div>}{error && <div className="error-state" role="alert"><strong>Unable to connect</strong><span>{error}</span><button className="text-link" onClick={() => window.location.reload()}>Try again</button></div>}{!loading && !error && data && <>{!hasData ? <section className="welcome-state"><div className="welcome-orbit"><Icon name="spark" /></div><div><p className="page-kicker">Your workspace is ready</p><h2>Start building your career signal.</h2><p>Add a resume or track your first opportunity to turn this dashboard into a live command center.</p><div className="empty-actions"><Link className="button button-small" to="/resumes">Add a resume <Icon name="arrow" /></Link><Link className="text-link" to="/jobs">Track a job</Link></div></div></section> : <><section className="stats-grid">{[['Total Applications', data.stats.total_applications, 'All roles in your pipeline', 'total'], ['Interviews', data.stats.interviews, 'Conversations booked', 'interviews'], ['Offers', data.stats.offers, 'Offers received', 'offers'], ['Rejections', data.stats.rejections, 'Closed opportunities', 'rejections'], ['Success Rate', `${data.stats.success_rate}%`, 'Offers per application', 'success']].map(([label, value, hint, key]) => <article className={`stat-card ${key}`} key={label as string}><span className="stat-icon"><Icon name={key === 'success' ? 'spark' : key === 'total' ? 'send' : key === 'interviews' ? 'mic' : key === 'offers' ? 'chart' : 'file'} /></span><span className="stat-label">{label}</span><strong>{value}</strong><small>{hint}</small></article>)}</section><div className="dashboard-columns"><section className="panel applications-panel"><PanelHeading title="Recent applications" link="View all" to="/applications" />{data.recent_applications.length ? <div className="application-list">{data.recent_applications.map((item) => <div className="application-row" key={item.id}><div className="company-avatar">{item.company.charAt(0)}</div><div className="row-main"><strong>{item.role}</strong><span>{item.company}</span></div><span className={`status status-${item.status}`}>{item.status}</span><time>{formatDate(item.updated_at)}</time></div>)}</div> : <InlineEmpty text="No applications yet" action="Track your first job" to="/jobs" />}</section><section className="panel interviews-panel"><PanelHeading title="Upcoming interviews" link="Prepare" to="/interview-prep" />{data.upcoming_interviews.length ? <div className="interview-list">{data.upcoming_interviews.map((item) => <div className="interview-row" key={item.id}><div className="date-tile"><strong>{new Date(item.scheduled_at).getDate()}</strong><span>{new Date(item.scheduled_at).toLocaleString('en-US', { month: 'short' })}</span></div><div><strong>{item.role}</strong><span>{item.company} <i /> {item.type}</span></div><time>{formatTime(item.scheduled_at)}</time></div>)}</div> : <InlineEmpty text="Your calendar is clear" action="Add an interview" to="/applications" />}</section><section className="panel skill-panel"><PanelHeading title="Skill gap summary" link="Explore gaps" to="/skill-gap" />{data.skill_gaps.length ? <div className="skill-list">{data.skill_gaps.map((item) => <div className="skill-row" key={item.id}><span>{item.skill}</span><div className="priority-bar"><i style={{ width: `${item.priority * 20}%` }} /></div><small>{item.priority}/5</small></div>)}</div> : <InlineEmpty text="No skill gaps identified" action="Analyze a role" to="/skill-gap" />}</section><section className="panel activity-panel"><PanelHeading title="Application activity" link="See analytics" to="/analytics" />{data.activity.length ? <div className="activity-chart"><div className="chart-bars">{data.activity.slice().reverse().map((item, index) => <div className="chart-column" key={`${item.date}-${index}`}><span style={{ height: `${Math.max(18, ((data.activity.length - index) / data.activity.length) * 100)}%` }} /><small>{new Date(item.date).toLocaleString('en-US', { weekday: 'short' }).slice(0, 2)}</small></div>)}</div><p><strong>{data.stats.total_applications}</strong> applications in your pipeline</p></div> : <InlineEmpty text="Activity appears as you apply" action="Find a role" to="/jobs" />}</section></div></>}</>}</main>
}

function PanelHeading({ title, link, to }: { title: string; link: string; to: string }) { return <div className="panel-heading"><h2>{title}</h2><Link to={to}>{link} <Icon name="arrow" /></Link></div> }
function InlineEmpty({ text, action, to }: { text: string; action: string; to: string }) { return <div className="inline-empty"><span>{text}</span><Link to={to}>{action} <Icon name="arrow" /></Link></div> }

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <main className="loading-page">Loading your workspace...</main>
  return user ? children : <Navigate to="/login" replace state={{ from: location.pathname }} />
}

function AccessPage({ register = false }: { register?: boolean }) {
  const { user, login, register: createAccount } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  if (user) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (register && password !== confirmPassword) { setError('Passwords do not match'); return }
    setSubmitting(true)
    try {
      if (register) await createAccount({ name, email, password, confirm_password: confirmPassword })
      else await login({ email, password })
      const destination = (location.state as { from?: string } | null)?.from ?? '/dashboard'
      navigate(destination, { replace: true })
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Unable to complete your request.'))
    } finally { setSubmitting(false) }
  }

  return <main className="access-page"><div className="access-card"><Link className="brand" to="/"><span className="brand-mark">CP</span><span>CareerPilot</span></Link><div className="eyebrow"><span className="status-dot" /> CareerPilot account</div><h1>{register ? 'Start with a clear next step.' : 'Welcome back.'}</h1><p>{register ? 'Create your workspace and make the search feel more intentional.' : 'Pick up where you left off.'}</p><form onSubmit={submit}>{register && <label>Name<input required value={name} onChange={(event) => setName(event.target.value)} type="text" placeholder="Your name" /></label>}<label>Email<input required value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="you@example.com" /></label><label>Password<input required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="At least 8 characters" /></label>{!register && <div className="forgot-password-link-row"><Link to="/forgot-password" className="forgot-password-link">Forgot password?</Link></div>}{register && <label>Confirm password<input required minLength={8} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} type="password" placeholder="Repeat your password" /></label>}{error && <p className="form-error" role="alert">{error}</p>}<button className="button" disabled={submitting} type="submit">{submitting ? 'Working...' : register ? 'Create account' : 'Log in'} <Icon name="arrow" /></button></form><p className="form-switch">{register ? 'Already have an account?' : 'New to CareerPilot?'} <Link to={register ? '/login' : '/register'}>{register ? 'Log in' : 'Get started'}</Link></p></div></main>
}

function ForgotPasswordPage() {
  const { user } = useAuth()
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null)
  const [error, setError] = useState('')

  if (user) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const response = await forgotPassword(email)
      setSubmitted(true)
      if (response.dev_reset_url) {
        setDevResetUrl(response.dev_reset_url)
      }
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Unable to process your request. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="access-page">
      <div className="access-card">
        <Link className="brand" to="/"><span className="brand-mark">CP</span><span>CareerPilot</span></Link>
        <div className="eyebrow"><span className="status-dot" /> Account recovery</div>
        <h1>Forgot Password</h1>
        <p>Enter your registered email address and we'll help you reset your password.</p>

        {submitted ? (
          <div className="password-reset-status-card" role="status">
            <p className="success-banner">
              If an account exists for this email address, a password reset link has been generated.
            </p>
            {devResetUrl && (
              <div className="dev-reset-notice">
                <small>Local development link:</small>
                <Link to={devResetUrl.replace(/^https?:\/\/[^/]+/, '')} className="dev-reset-link">
                  Open Reset Password Link
                </Link>
              </div>
            )}
            <p className="form-switch">
              Remember your password? <Link to="/login">Return to login</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label>
              Email
              <input
                required
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                disabled={submitting}
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button" disabled={submitting} type="submit">
              {submitting ? 'Sending...' : 'Send Reset Link'} <Icon name="arrow" />
            </button>
            <p className="form-switch">
              Remember your password? <Link to="/login">Back to login</Link>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}

function ResetPasswordPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  if (user) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (!token) {
      setError('Password reset token is missing or invalid. Please request a new link.')
      return
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      await resetPassword(token, newPassword, confirmPassword)
      setSubmitted(true)
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Unable to reset password. The link may have expired or already been used.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="access-page">
      <div className="access-card">
        <Link className="brand" to="/"><span className="brand-mark">CP</span><span>CareerPilot</span></Link>
        <div className="eyebrow"><span className="status-dot" /> Secure password reset</div>
        <h1>Set New Password</h1>
        <p>Choose a strong new password for your CareerPilot account.</p>

        {!token ? (
          <div className="password-reset-status-card">
            <p className="form-error" role="alert">
              No reset token found. Please check your reset link or request a new one.
            </p>
            <div className="form-actions-center">
              <Link className="button button-small" to="/forgot-password">
                Request new link <Icon name="arrow" />
              </Link>
            </div>
          </div>
        ) : submitted ? (
          <div className="password-reset-status-card" role="status">
            <p className="success-banner">
              Your password has been reset successfully. You can now log in with your new password.
            </p>
            <div className="form-actions-center">
              <Link className="button" to="/login">
                Return to Login <Icon name="arrow" />
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label>
              New Password
              <input
                required
                type="password"
                minLength={8}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="At least 8 characters"
                disabled={submitting}
              />
            </label>
            <label>
              Confirm New Password
              <input
                required
                type="password"
                minLength={8}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Repeat your new password"
                disabled={submitting}
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button" disabled={submitting} type="submit">
              {submitting ? 'Resetting...' : 'Reset Password'} <Icon name="arrow" />
            </button>
            <p className="form-switch">
              Remember your password? <Link to="/login">Back to login</Link>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}

function App() {
  return <Shell><Routes><Route path="/" element={<LandingPage />} /><Route path="/login" element={<AccessPage />} /><Route path="/register" element={<AccessPage register />} /><Route path="/forgot-password" element={<ForgotPasswordPage />} /><Route path="/reset-password" element={<ResetPasswordPage />} /><Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} /><Route path="/resumes" element={<ProtectedRoute><ResumesPage /></ProtectedRoute>} /><Route path="/jobs" element={<ProtectedRoute><JobsPage /></ProtectedRoute>} /><Route path="/jobs/:id" element={<ProtectedRoute><JobDetailsPage /></ProtectedRoute>} /><Route path="/applications" element={<ProtectedRoute><ApplicationsPage /></ProtectedRoute>} /><Route path="/automation" element={<ProtectedRoute><AutomationDashboard /></ProtectedRoute>} /><Route path="/analysis" element={<ProtectedRoute><AnalysisPage /></ProtectedRoute>} /><Route path="/skill-gap" element={<ProtectedRoute><SkillGapPage /></ProtectedRoute>} /><Route path="/interview-prep" element={<ProtectedRoute><InterviewPrepPage /></ProtectedRoute>} /><Route path="/mock-interview" element={<ProtectedRoute><MockInterviewPage /></ProtectedRoute>} /><Route path="/assistant" element={<ProtectedRoute><AssistantPage /></ProtectedRoute>} />{navItems.slice(10).map((item) => <Route key={item.to} path={item.to} element={<ProtectedRoute><PlaceholderPage title={item.label} description="This workspace is ready for your career data and next best action." /></ProtectedRoute>} />)}<Route path="*" element={<LandingPage />} /></Routes></Shell>
}

export default App
