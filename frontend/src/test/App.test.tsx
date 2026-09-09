import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AuthProvider } from '../lib/auth'
import { api, AUTH_TOKEN_KEY } from '../lib/api'

const user = { id: 'user-1', name: 'Ada Lovelace', email: 'ada@example.com', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
const resume = { id: 'resume-1', filename: 'resume.pdf', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', is_active: true, extracted_text: 'Python', extracted_text_preview: 'Python' }
const job = { id: 'job-1', title: 'Backend Engineer', company: 'CareerPilot', description: 'Python APIs', url: null, location: 'Remote', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
const application = { id: 'application-1', job_id: job.id, title: job.title, company: job.company, location: job.location, status: 'wishlist' as const, application_date: null, interview_date: null, salary: null, recruiter_name: null, recruiter_email: null, notes: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }

function renderApp(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>)
}

function mockAuthenticatedApi() {
  sessionStorage.setItem(AUTH_TOKEN_KEY, 'test-token')
  vi.spyOn(api, 'get').mockImplementation(async (path) => {
    if (path === '/auth/me') return { data: user } as never
    if (path === '/dashboard') return { data: { stats: { total_applications: 0, interviews: 0, offers: 0, rejections: 0, success_rate: 0 }, recent_applications: [], upcoming_interviews: [], skill_gaps: [], activity: [] } } as never
    if (path === '/resumes') return { data: [resume] } as never
    if (path === '/jobs') return { data: [job] } as never
    if (path === '/applications') return { data: [application] } as never
    return { data: [] } as never
  })
}

describe('CareerPilot application flows', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('redirects an unauthenticated visitor from a protected route', async () => {
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
  })

  it('logs in and navigates to the protected dashboard', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: { access_token: 'new-token', user } } as never)
    const client = userEvent.setup()
    renderApp('/login')

    await client.type(screen.getByLabelText('Email'), user.email)
    await client.type(screen.getByLabelText('Password'), 'correct-password')
    await client.click(screen.getByRole('button', { name: /log in/i }))

    expect(await screen.findByRole('heading', { name: /good morning, ada/i })).toBeInTheDocument()
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('new-token')
  })

  it('creates an application from a saved job', async () => {
    mockAuthenticatedApi()
    vi.spyOn(api, 'post').mockResolvedValue({ data: application } as never)
    const client = userEvent.setup()
    renderApp('/applications')

    await client.click(await screen.findByRole('button', { name: /add application/i }))
    const addButtons = screen.getAllByRole('button', { name: /add application/i })
    await client.click(addButtons[addButtons.length - 1])

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/applications', expect.objectContaining({ job_id: job.id, status: 'wishlist' })))
  })

  it('rejects a non-PDF before attempting a resume upload', async () => {
    mockAuthenticatedApi()
    const post = vi.spyOn(api, 'post')
    renderApp('/resumes')
    const fileInput = await waitFor(() => {
      const element = document.querySelector('input[type="file"]')
      if (!element) throw new Error('Resume file input was not rendered')
      return element as HTMLInputElement
    })
    fireEvent.change(fileInput, { target: { files: [new File(['text'], 'resume.txt', { type: 'text/plain' })] } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/only pdf files/i)
    expect(post).not.toHaveBeenCalled()
  })

  it('uploads a valid resume and displays it in the library', async () => {
    mockAuthenticatedApi()
    vi.spyOn(api, 'post').mockResolvedValue({ data: { ...resume, id: 'resume-2', filename: 'new-resume.pdf' } } as never)
    const client = userEvent.setup()
    renderApp('/resumes')
    const fileInput = await waitFor(() => {
      const element = document.querySelector('input[type="file"]')
      if (!element) throw new Error('Resume file input was not rendered')
      return element as HTMLInputElement
    })
    await client.upload(fileInput, new File(['%PDF-1.7'], 'new-resume.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText('new-resume.pdf')).toBeInTheDocument()
  })

  it('runs analysis and renders match results', async () => {
    mockAuthenticatedApi()
    vi.spyOn(api, 'post').mockResolvedValue({ data: { id: 'analysis-1', resume_id: resume.id, job_id: job.id, match_percentage: 82, matching_skills: ['Python'], missing_skills: ['Docker'], missing_keywords: [], relevant_experience_keywords: [], recommended_skills: [], resume_improvement_suggestions: [], created_at: '2026-01-01T00:00:00Z' } } as never)
    const client = userEvent.setup()
    renderApp('/analysis')
    await client.click(await screen.findByRole('button', { name: /analyze match/i }))
    expect(await screen.findByText('82%')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Docker')).toBeInTheDocument()
  })

  it('shows login validation errors returned by the API', async () => {
    vi.spyOn(api, 'post').mockRejectedValue({ response: { data: { detail: 'Invalid credentials' } } })
    const client = userEvent.setup()
    renderApp('/login')
    await client.type(screen.getByLabelText('Email'), user.email)
    await client.type(screen.getByLabelText('Password'), 'wrong-password')
    await client.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials')
  })
})