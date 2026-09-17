import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AutomationDashboard } from '../components/AutomationDashboard'
import { api } from '../lib/api'

const mockProfile = {
  id: 'prof-1',
  user_id: 'user-1',
  full_name: 'Ada Lovelace',
  email: 'ada@example.com',
  phone: '+1 555-0199',
  location: 'London, UK',
  linkedin_url: 'https://linkedin.com/in/ada',
  github_url: 'https://github.com/ada',
  portfolio_url: 'https://ada.dev',
  work_authorization: 'US Citizen / Authorized',
  requires_sponsorship: false,
  demographic_sharing_opt_in: false,
  years_of_experience: 5,
  education_degree: 'Bachelor of Science',
  education_field: 'Computer Science',
  education_school: 'University of London',
  answers_json: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const mockSetting = {
  id: 'set-1',
  user_id: 'user-1',
  is_enabled: true,
  schedule_interval: 'hourly',
  auto_submit: false,
  allowed_companies_json: '["Google", "Stripe"]',
  max_daily_applications: 10,
  delay_between_actions_ms: 1000,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const mockRun = {
  id: 'run-1',
  user_id: 'user-1',
  job_id: 'job-1',
  application_id: null,
  company: 'DeepTech',
  job_title: 'Senior AI Engineer',
  job_url: 'https://careers.deeptech.io/jobs/1',
  status: 'waiting_for_user',
  current_step: 'fill_fields',
  error_message: null,
  requires_user_action: true,
  user_prompt: 'Sensitive demographic question requires your confirmation',
  user_prompt_context_json: null,
  suggested_action_json: null,
  user_response_json: null,
  screenshot_path: null,
  scenarios_used_count: 2,
  started_at: '2026-01-01T00:00:00Z',
  completed_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AutomationDashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/automation/runs') return { data: [mockRun] } as never
      if (path === '/automation/profile') return { data: mockProfile } as never
      if (path === '/automation/settings') return { data: mockSetting } as never
      if (path === '/automation/scenarios') return { data: [] } as never
      if (path === '/jobs') return { data: [{ id: 'job-1', title: 'Senior AI Engineer', company: 'DeepTech' }] } as never
      return { data: [] } as never
    })
  })

  it('renders automation dashboard and tabs', async () => {
    render(<AutomationDashboard />)

    expect(await screen.findByRole('heading', { name: /application automation/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /runs & status/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /scenario memory/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /profile & settings/i })).toBeInTheDocument()
  })

  it('shows intervention tab and displays waiting run details', async () => {
    const client = userEvent.setup()
    render(<AutomationDashboard />)

    const interventionTab = await screen.findByRole('button', { name: /human intervention/i })
    expect(interventionTab).toBeInTheDocument()
    await client.click(interventionTab)

    expect(await screen.findByText(/human input required/i)).toBeInTheDocument()
    expect(screen.getByText(/sensitive demographic question requires your confirmation/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject & stop/i })).toBeInTheDocument()
  })

  it('navigates to Profile & Settings and renders candidate details', async () => {
    const client = userEvent.setup()
    render(<AutomationDashboard />)

    const settingsTab = await screen.findByRole('button', { name: /profile & settings/i })
    await client.click(settingsTab)

    expect(await screen.findByDisplayValue('+1 555-0199')).toBeInTheDocument()
    expect(screen.getByDisplayValue('London, UK')).toBeInTheDocument()
    expect(screen.getByDisplayValue('https://linkedin.com/in/ada')).toBeInTheDocument()
  })

  it('navigates to Job Search tab and displays search configuration and candidates', async () => {
    const client = userEvent.setup()
    render(<AutomationDashboard />)

    const searchTab = await screen.findByRole('button', { name: /job search/i })
    expect(searchTab).toBeInTheDocument()
    await client.click(searchTab)

    expect(await screen.findByRole('heading', { name: /job search & multi-job discovery/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/e\.g\. software developer/i)).toBeInTheDocument()
    expect(screen.getByText(/min match score/i)).toBeInTheDocument()
    expect(screen.getByText(/skip already applied postings/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /discover jobs/i })).toBeInTheDocument()
  })
})
