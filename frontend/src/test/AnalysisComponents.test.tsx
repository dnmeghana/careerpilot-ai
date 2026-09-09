import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AnalysisRequestSelector } from '../components/AnalysisRequestSelector'
import { AnalysisResultsCard } from '../components/AnalysisResultsCard'

const resume = { id: 'resume-1', filename: 'resume.pdf', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', is_active: true, extracted_text: null, extracted_text_preview: '' }
const job = { id: 'job-1', title: 'Backend Engineer', company: 'CareerPilot', description: 'Python APIs', url: null, location: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }

 describe('analysis components', () => {
  it('selects a resume and job before starting analysis', async () => {
    const onResumeSelect = vi.fn()
    const onJobSelect = vi.fn()
    const onAnalyze = vi.fn()
    const client = userEvent.setup()
    render(<AnalysisRequestSelector resumes={[resume]} jobs={[job]} selectedResumeId={null} selectedJobId={null} isLoading={false} onResumeSelect={onResumeSelect} onJobSelect={onJobSelect} onAnalyze={onAnalyze} />)

    expect(screen.getByRole('button', { name: /analyze match/i })).toBeDisabled()
    await client.click(screen.getByRole('button', { name: /choose a resume/i }))
    await client.click(screen.getByRole('button', { name: /resume\.pdf/i }))
    await client.click(screen.getByRole('button', { name: /choose a job/i }))
    await client.click(screen.getByRole('button', { name: /backend engineer/i }))

    expect(onResumeSelect).toHaveBeenCalledWith(resume.id)
    expect(onJobSelect).toHaveBeenCalledWith(job.id)
  })

  it('renders match percentage and skill recommendations', () => {
    render(<AnalysisResultsCard analysis={{ id: 'analysis-1', resume_id: resume.id, job_id: job.id, match_percentage: 80, matching_skills: ['Python'], missing_skills: ['Docker'], missing_keywords: [], relevant_experience_keywords: [], recommended_skills: ['Kubernetes'], resume_improvement_suggestions: ['Add measurable outcomes'], created_at: '2026-01-01T00:00:00Z' }} isLoading={false} />)

    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Docker')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes')).toBeInTheDocument()
    expect(screen.getByText('Add measurable outcomes')).toBeInTheDocument()
  })
})
