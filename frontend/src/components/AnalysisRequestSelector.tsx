import { useState } from 'react'
import { ChevronDown, Loader2, Sparkles } from 'lucide-react'
import type { Resume, Job } from '../lib/api'

interface AnalysisRequestSelectorProps {
  resumes: Resume[]
  jobs: Job[]
  selectedResumeId: string | null
  selectedJobId: string | null
  isLoading: boolean
  onResumeSelect: (resumeId: string) => void
  onJobSelect: (jobId: string) => void
  onAnalyze: () => void
  disabled?: boolean
}

export function AnalysisRequestSelector({
  resumes,
  jobs,
  selectedResumeId,
  selectedJobId,
  isLoading,
  onResumeSelect,
  onJobSelect,
  onAnalyze,
  disabled = false,
}: AnalysisRequestSelectorProps) {
  const [showResumeDropdown, setShowResumeDropdown] = useState(false)
  const [showJobDropdown, setShowJobDropdown] = useState(false)

  const selectedResume = resumes.find((r) => r.id === selectedResumeId)
  const selectedJob = jobs.find((j) => j.id === selectedJobId)

  const canAnalyze = selectedResumeId && selectedJobId && !isLoading && !disabled

  return (
    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Resume vs Job Analysis</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Resume Selector */}
        <div className="relative">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Resume</label>
          <div className="relative">
            <button
              onClick={() => setShowResumeDropdown(!showResumeDropdown)}
              className="w-full px-4 py-2 text-left bg-white border border-gray-300 rounded-lg hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between"
            >
              <span className={selectedResume ? 'text-gray-900' : 'text-gray-500'}>
                {selectedResume ? selectedResume.filename : 'Choose a resume...'}
              </span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>

            {showResumeDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-50">
                {resumes.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-gray-500">No resumes available</div>
                ) : (
                  <ul className="max-h-48 overflow-y-auto">
                    {resumes.map((resume) => (
                      <li key={resume.id}>
                        <button
                          onClick={() => {
                            onResumeSelect(resume.id)
                            setShowResumeDropdown(false)
                          }}
                          className={`w-full text-left px-4 py-2 hover:bg-blue-50 ${
                            selectedResumeId === resume.id ? 'bg-blue-100 text-blue-900 font-medium' : 'text-gray-700'
                          }`}
                        >
                          {resume.filename}
                          {resume.is_active && <span className="text-xs text-gray-500 ml-2">(active)</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Job Selector */}
        <div className="relative">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Job</label>
          <div className="relative">
            <button
              onClick={() => setShowJobDropdown(!showJobDropdown)}
              className="w-full px-4 py-2 text-left bg-white border border-gray-300 rounded-lg hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between"
            >
              <span className={selectedJob ? 'text-gray-900' : 'text-gray-500'}>
                {selectedJob ? `${selectedJob.title} @ ${selectedJob.company}` : 'Choose a job...'}
              </span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>

            {showJobDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-50">
                {jobs.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-gray-500">No jobs available</div>
                ) : (
                  <ul className="max-h-48 overflow-y-auto">
                    {jobs.map((job) => (
                      <li key={job.id}>
                        <button
                          onClick={() => {
                            onJobSelect(job.id)
                            setShowJobDropdown(false)
                          }}
                          className={`w-full text-left px-4 py-2 hover:bg-blue-50 ${
                            selectedJobId === job.id ? 'bg-blue-100 text-blue-900 font-medium' : 'text-gray-700'
                          }`}
                        >
                          <div className="font-medium">{job.title}</div>
                          <div className="text-xs text-gray-500">{job.company}</div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Analyze Button */}
      <button
        onClick={onAnalyze}
        disabled={!canAnalyze}
        className={`w-full px-6 py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
          canAnalyze
            ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700 cursor-pointer'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Analyzing...
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Analyze Match
          </>
        )}
      </button>

      {!canAnalyze && selectedResumeId && selectedJobId && !isLoading && (
        <p className="text-xs text-gray-500 mt-2 text-center">Ready to analyze</p>
      )}
      {!selectedResumeId || (!selectedJobId && !isLoading && (
        <p className="text-xs text-gray-500 mt-2 text-center">Select both resume and job to continue</p>
      ))}
    </div>
  )
}
