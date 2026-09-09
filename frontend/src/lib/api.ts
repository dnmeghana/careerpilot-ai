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
export type Application = { id: string; job_id: string; title: string; company: string; location: string | null; status: ApplicationStatus; application_date: string | null; interview_date: string | null; salary: number | null; recruiter_name: string | null; recruiter_email: string | null; notes: string | null; created_at: string; updated_at: string }
export type ApplicationInput = { job_id: string; status: ApplicationStatus; application_date: string; interview_date: string; salary: number | null; recruiter_name: string; recruiter_email: string; notes: string }
export type ResumeJobAnalysis = { id: string; resume_id: string; job_id: string; match_percentage: number; matching_skills: string[]; missing_skills: string[]; missing_keywords: string[]; relevant_experience_keywords: string[]; recommended_skills: string[]; resume_improvement_suggestions: string[]; created_at: string }
export type SkillGap = { has_analysis: boolean; analysis_id: string | null; resume_id: string | null; job_id: string | null; resume_name: string | null; job_title: string | null; company: string | null; match_percentage: number; matching_skills: string[]; missing_skills: string[]; skill_priorities: { skill: string; priority: number }[]; recommended_learning_areas: string[]; created_at: string | null }
export const interviewTypes = ['HR', 'Behavioral', 'Technical', 'System Design'] as const
export type InterviewType = typeof interviewTypes[number]
export type InterviewQuestion = { id: string; question: string; category: string | null; difficulty: string | null; suggested_answer: string | null; completed: boolean }
export type Interview = { id: string; job_id: string; job_title: string; company: string; interview_type: InterviewType; scheduled_at: string; status: string; notes: string | null; created_at: string; updated_at: string; questions: InterviewQuestion[] }
export type MockInterviewQuestion = { id: string; question: string; category: string | null; difficulty: string | null; suggested_answer: string | null; answer: string; score: number | null; feedback: { strengths?: string[]; weaknesses?: string[]; suggestions?: string[] } | null }
export type MockInterview = { id: string; job_id: string | null; job_title: string | null; company: string | null; interview_type: string; started_at: string; completed_at: string | null; overall_score: number | null; current_question: number; questions: MockInterviewQuestion[]; strong_areas: string[]; weak_areas: string[]; recommendations: string[] }

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