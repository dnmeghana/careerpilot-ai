import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const AUTH_TOKEN_KEY = 'careerpilot_access_token'
export const MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024

export function getApiErrorMessage(error: unknown, fallback: string) {
  const response = axios.isAxiosError(error)
    ? error.response
    : typeof error === 'object' && error !== null && 'response' in error
      ? (error as { response?: { data?: { detail?: unknown } } }).response
      : undefined
  const detail = response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

export type Resume = {
  id: string
  filename: string
  created_at: string
  updated_at: string
  is_active: boolean
  extracted_text: string | null
  extracted_text_preview: string
}

export type Job = {
  id: string
  title: string
  company: string
  description: string | null
  url: string | null
  location: string | null
  created_at: string
  updated_at: string
}

export type JobInput = Omit<Job, 'id' | 'created_at' | 'updated_at'>

export const applicationStatuses = ['wishlist', 'applied', 'screening', 'interview', 'technical_interview', 'final_round', 'offer', 'rejected'] as const
export type ApplicationStatus = typeof applicationStatuses[number]
export type Application = {
  id: string
  job_id: string
  title: string
  company: string
  location: string | null
  status: ApplicationStatus
  application_date: string | null
  interview_date: string | null
  salary: number | null
  recruiter_name: string | null
  recruiter_email: string | null
  notes: string | null
  created_at: string
  updated_at: string
  automation_status?: string | null
  last_automation_attempt?: string | null
}
export type ApplicationInput = { job_id: string; status: ApplicationStatus; application_date: string; interview_date: string; salary: number | null; recruiter_name: string; recruiter_email: string; notes: string }
export type ResumeJobAnalysis = { id: string; resume_id: string; job_id: string; match_percentage: number; matching_skills: string[]; missing_skills: string[]; missing_keywords: string[]; relevant_experience_keywords: string[]; recommended_skills: string[]; resume_improvement_suggestions: string[]; created_at: string }
export type SkillGap = { has_analysis: boolean; analysis_id: string | null; resume_id: string | null; job_id: string | null; resume_name: string | null; job_title: string | null; company: string | null; match_percentage: number; matching_skills: string[]; missing_skills: string[]; skill_priorities: { skill: string; priority: number }[]; recommended_learning_areas: string[]; created_at: string | null }
export const interviewTypes = ['HR', 'Behavioral', 'Technical', 'System Design'] as const
export type InterviewType = typeof interviewTypes[number]
export type InterviewQuestion = { id: string; question: string; category: string | null; difficulty: string | null; suggested_answer: string | null; completed: boolean }
export type Interview = { id: string; job_id: string; job_title: string; company: string; interview_type: InterviewType; scheduled_at: string; status: string; notes: string | null; created_at: string; updated_at: string; questions: InterviewQuestion[] }
export type MockInterviewQuestion = { id: string; question: string; category: string | null; difficulty: string | null; suggested_answer: string | null; answer: string; score: number | null; feedback: { strengths?: string[]; weaknesses?: string[]; suggestions?: string[] } | null }
export type MockInterview = { id: string; job_id: string | null; job_title: string | null; company: string | null; interview_type: string; started_at: string; completed_at: string | null; overall_score: number | null; current_question: number; questions: MockInterviewQuestion[]; strong_areas: string[]; weak_areas: string[]; recommendations: string[] }

export type CandidateProfile = {
  id: string
  user_id: string
  phone: string | null
  location: string | null
  linkedin_url: string | null
  github_url: string | null
  portfolio_url: string | null
  work_authorization: string | null
  requires_sponsorship: boolean | null
  demographic_sharing_opt_in: boolean
  years_of_experience: number | null
  education_degree: string | null
  education_field: string | null
  education_school: string | null
  answers_json: string | null
  created_at: string
  updated_at: string
}

export type AutomationActionLog = {
  id: string
  run_id: string
  action_type: string
  action_source: string
  step_name: string | null
  selector_used: string | null
  value_used: string | null
  confidence: string
  confidence_reason: string | null
  result: string
  error_message: string | null
  screenshot_path: string | null
  current_url?: string | null
  page_title?: string | null
  created_at: string
}

export type AutomationRun = {
  id: string
  user_id: string
  job_id: string | null
  application_id: string | null
  company: string
  job_title: string
  job_url: string | null
  current_url?: string | null
  page_title?: string | null
  status: string
  current_step: string | null
  error_message: string | null
  requires_user_action: boolean
  user_prompt: string | null
  user_prompt_context_json: string | null
  suggested_action_json: string | null
  user_response_json: string | null
  screenshot_path: string | null
  scenarios_used_count: number
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
  action_logs?: AutomationActionLog[]
}

export type AutomationScenario = {
  id: string
  user_id: string | null
  company: string
  page_signature: string
  field_key: string
  element_strategy_json: string
  action_type: string
  value_source: string
  static_value: string | null
  confidence: string
  confidence_reason: string | null
  version: number
  is_active: boolean
  is_approved: boolean
  times_used: number
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export type AutomationSetting = {
  id: string
  user_id: string
  is_enabled: boolean
  schedule_interval: string
  auto_submit: boolean
  allowed_companies_json: string | null
  max_daily_applications: number
  delay_between_actions_ms: number
  created_at: string
  updated_at: string
}

export async function getResumes() {
  const response = await api.get<Resume[]>('/resumes')
  return response.data
}

export async function uploadResume(file: File, onProgress: (progress: number) => void) {
  const form = new FormData()
  form.append('file', file)
  const response = await api.post<Resume>('/resumes', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => event.total && onProgress(Math.round((event.loaded / event.total) * 100)),
  })
  return response.data
}

export async function analyzeResumeVsJob(resumeId: string, jobId: string) {
  const response = await api.post<ResumeJobAnalysis>('/analysis/resume-job', {
    resume_id: resumeId,
    job_id: jobId,
  })
  return response.data
}

export async function getSkillGap() {
  const response = await api.get<SkillGap>('/analysis/skill-gap')
  return response.data
}

export async function getCandidateProfile() {
  const response = await api.get<CandidateProfile>('/automation/profile')
  return response.data
}

export async function updateCandidateProfile(payload: Partial<CandidateProfile>) {
  const response = await api.put<CandidateProfile>('/automation/profile', payload)
  return response.data
}

export async function getAutomationRuns(statusFilter?: string) {
  const response = await api.get<AutomationRun[]>('/automation/runs', {
    params: statusFilter ? { status: statusFilter } : undefined,
  })
  return response.data
}

export async function getAutomationRun(runId: string) {
  const response = await api.get<AutomationRun>(`/automation/runs/${runId}`)
  return response.data
}

export async function triggerAutomationRun(payload: { job_id?: string; job_url?: string; company?: string; job_title?: string }) {
  const response = await api.post<AutomationRun>('/automation/runs/trigger', payload)
  return response.data
}

export async function pauseAutomationRun(runId: string) {
  const response = await api.post<AutomationRun>(`/automation/runs/${runId}/pause`)
  return response.data
}

export async function resumeAutomationRun(runId: string) {
  const response = await api.post<AutomationRun>(`/automation/runs/${runId}/resume`)
  return response.data
}

export async function interveneAutomationRun(runId: string, action: string, value?: string, rememberScenario = true) {
  const response = await api.post<AutomationRun>(`/automation/runs/${runId}/intervene`, {
    action,
    value,
    remember_scenario: rememberScenario,
  })
  return response.data
}

export async function getAutomationScenarios(company?: string) {
  const response = await api.get<AutomationScenario[]>('/automation/scenarios', {
    params: company ? { company } : undefined,
  })
  return response.data
}

export async function updateAutomationScenario(scenarioId: string, updates: Partial<AutomationScenario>) {
  const response = await api.patch<AutomationScenario>(`/automation/scenarios/${scenarioId}`, updates)
  return response.data
}

export async function deleteAutomationScenario(scenarioId: string) {
  await api.delete(`/automation/scenarios/${scenarioId}`)
}

export async function getAutomationSettings() {
  const response = await api.get<AutomationSetting>('/automation/settings')
  return response.data
}

export async function updateAutomationSettings(payload: Partial<AutomationSetting>) {
  const response = await api.put<AutomationSetting>('/automation/settings', payload)
  return response.data
}

export type JobSearchConfig = {
  id: string
  user_id: string
  desired_job_title: string
  desired_location: string
  years_of_experience: number
  platform_search_url: string
  specific_company?: string | null
  active_resume_id?: string | null
  max_jobs_to_discover: number
  min_match_score?: number
  skip_already_applied?: boolean
  schedule_interval?: string
  is_active: boolean
  last_searched_at?: string | null
  created_at: string
  updated_at: string
}

export type DiscoveredJob = {
  id: string
  user_id: string
  config_id?: string | null
  company: string
  exact_title: string
  job_url: string
  location?: string | null
  requisition_id?: string | null
  experience_raw?: string | null
  platform: string
  raw_description?: string | null
  match_score: number
  title_score: number
  skills_score: number
  location_score: number
  experience_score: number
  is_matched: boolean
  match_reasons_json?: string | null
  match_breakdown_json?: string | null
  matched_skills_json?: string | null
  missing_skills_json?: string | null
  matched_skills?: string[]
  missing_skills?: string[]
  status: string
  automation_run_id?: string | null
  discovered_at: string
  updated_at: string
}

export async function getJobSearchConfig() {
  const response = await api.get<JobSearchConfig | null>('/automation/search/config')
  return response.data
}

export async function saveJobSearchConfig(payload: {
  desired_job_title: string
  desired_location: string
  years_of_experience: number
  platform_search_url: string
  specific_company?: string
  active_resume_id?: string
  max_jobs_to_discover?: number
  min_match_score?: number
  skip_already_applied?: boolean
  schedule_interval?: string
}) {
  const response = await api.post<JobSearchConfig>('/automation/search/config', payload)
  return response.data
}

export async function triggerJobDiscovery(payload?: {
  config_id?: string
  search_url?: string
  max_results?: number
  min_match_score?: number
  skip_already_applied?: boolean
}) {
  const response = await api.post<{
    total_discovered: number
    total_matched: number
    new_candidates_saved: number
    jobs: DiscoveredJob[]
  }>('/automation/search/discover', payload || {})
  return response.data
}

export async function getDiscoveredJobs(statusFilter?: string) {
  const response = await api.get<DiscoveredJob[]>('/automation/search/jobs', {
    params: statusFilter ? { status: statusFilter } : undefined,
  })
  return response.data
}

export async function queueDiscoveredJob(jobId: string) {
  const response = await api.post<DiscoveredJob>(`/automation/search/jobs/${jobId}/queue`)
  return response.data
}

export async function applyDiscoveredJob(jobId: string) {
  const response = await api.post<AutomationRun>(`/automation/search/jobs/${jobId}/apply`)
  return response.data
}

export type ForgotPasswordResponse = {
  message: string
  dev_reset_url?: string | null
}

export type ResetPasswordResponse = {
  message: string
}

export async function forgotPassword(email: string): Promise<ForgotPasswordResponse> {
  const response = await api.post<ForgotPasswordResponse>('/auth/forgot-password', { email })
  return response.data
}

export async function resetPassword(
  token: string,
  new_password: string,
  confirm_password: string,
): Promise<ResetPasswordResponse> {
  const response = await api.post<ResetPasswordResponse>('/auth/reset-password', {
    token,
    new_password,
    confirm_password,
  })
  return response.data
}

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem(AUTH_TOKEN_KEY)
      window.dispatchEvent(new Event('careerpilot:unauthorized'))
    }
    return Promise.reject(error)
  },
)