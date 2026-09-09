import { Loader2 } from 'lucide-react'
import type { ResumeJobAnalysis } from '../lib/api'
import './Analysis.css'

interface AnalysisResultsCardProps {
  analysis: ResumeJobAnalysis | null
  isLoading: boolean
}

export function AnalysisResultsCard({ analysis, isLoading }: AnalysisResultsCardProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <p className="mt-4 text-gray-600">Analyzing resume and job description...</p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="text-center py-12 text-gray-500">
        <p>No analysis available yet. Select a resume and job to get started.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Match Percentage */}
      <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-6 rounded-lg border border-blue-200">
        <h3 className="text-sm font-medium text-gray-600 mb-2">Overall Match</h3>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <div className="relative w-full bg-gray-300 rounded-full h-4">
              <div
                className="bg-gradient-to-r from-blue-500 to-blue-600 h-4 rounded-full transition-all duration-500"
                style={{ width: `${analysis.match_percentage}%` }}
              />
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-blue-600">{analysis.match_percentage}%</div>
            <p className="text-xs text-gray-500">match</p>
          </div>
        </div>
      </div>

      {/* Matching Skills */}
      {analysis.matching_skills.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="text-green-500">✓</span> Matching Skills
          </h3>
          <div className="flex flex-wrap gap-2">
            {analysis.matching_skills.map((skill) => (
              <span
                key={skill}
                className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium border border-green-300"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Missing Skills */}
      {analysis.missing_skills.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="text-yellow-500">⚠</span> Missing Skills
          </h3>
          <div className="flex flex-wrap gap-2">
            {analysis.missing_skills.map((skill) => (
              <span
                key={skill}
                className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-medium border border-yellow-300"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Missing Keywords */}
      {analysis.missing_keywords.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="text-orange-500">⚠</span> Missing Keywords
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {analysis.missing_keywords.map((keyword) => (
              <div key={keyword} className="px-3 py-2 bg-orange-50 text-orange-700 rounded border border-orange-300 text-xs">
                {keyword}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relevant Experience Keywords */}
      {analysis.relevant_experience_keywords.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="text-blue-500">✓</span> Relevant Experience
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {analysis.relevant_experience_keywords.map((keyword) => (
              <div key={keyword} className="px-3 py-2 bg-blue-50 text-blue-700 rounded border border-blue-300 text-xs">
                {keyword}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Skills */}
      {analysis.recommended_skills.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Recommended Skills to Learn</h3>
          <ul className="space-y-2">
            {analysis.recommended_skills.map((skill) => (
              <li key={skill} className="flex items-center gap-2 text-sm text-gray-700">
                <span className="inline-block w-2 h-2 bg-purple-500 rounded-full" />
                {skill}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Improvement Suggestions */}
      {analysis.resume_improvement_suggestions.length > 0 && (
        <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Resume Improvement Suggestions</h3>
          <ul className="space-y-2">
            {analysis.resume_improvement_suggestions.map((suggestion, idx) => (
              <li key={idx} className="flex gap-3 text-sm text-gray-700">
                <span className="text-blue-500 font-bold flex-shrink-0">{idx + 1}.</span>
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Metadata */}
      <div className="text-xs text-gray-400 border-t pt-4">
        <p>Analysis generated on {new Date(analysis.created_at).toLocaleDateString()}</p>
      </div>
    </div>
  )
}
