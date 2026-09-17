import { useEffect, useState, type FormEvent } from 'react'
import {
  getCandidateProfile,
  updateCandidateProfile,
  getAutomationRuns,
  getAutomationRun,
  triggerAutomationRun,
  pauseAutomationRun,
  resumeAutomationRun,
  interveneAutomationRun,
  getAutomationScenarios,
  updateAutomationScenario,
  deleteAutomationScenario,
  getAutomationSettings,
  updateAutomationSettings,
  getJobSearchConfig,
  saveJobSearchConfig,
  triggerJobDiscovery,
  getDiscoveredJobs,
  queueDiscoveredJob,
  applyDiscoveredJob,
  getResumes,
  api,
  type AutomationRun,
  type AutomationScenario,
  type AutomationSetting,
  type CandidateProfile,
  type Job,
  type JobSearchConfig,
  type DiscoveredJob,
  type Resume,
} from '../lib/api'
import { Icon } from './Icon'

type TabType = 'runs' | 'search' | 'interventions' | 'memory' | 'settings'

export function AutomationDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('runs')
  const [runs, setRuns] = useState<AutomationRun[]>([])
  const [scenarios, setScenarios] = useState<AutomationScenario[]>([])
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [settings, setSettings] = useState<AutomationSetting | null>(null)
  const [savedJobs, setSavedJobs] = useState<Job[]>([])

  // Job Search & Discovery State
  const [searchConfig, setSearchConfig] = useState<JobSearchConfig | null>(null)
  const [discoveredJobs, setDiscoveredJobs] = useState<DiscoveredJob[]>([])
  const [resumes, setResumes] = useState<Resume[]>([])
  const [desiredJobTitle, setDesiredJobTitle] = useState('')
  const [desiredLocation, setDesiredLocation] = useState('')
  const [yearsOfExp, setYearsOfExp] = useState<number>(3)
  const [platformSearchUrl, setPlatformSearchUrl] = useState('')
  const [specificCompany, setSpecificCompany] = useState('')
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [maxJobs, setMaxJobs] = useState<number>(10)
  const [minMatchScore, setMinMatchScore] = useState<number>(60)
  const [skipAlreadyApplied, setSkipAlreadyApplied] = useState<boolean>(true)
  const [scheduleInterval, setScheduleInterval] = useState<string>('manual')
  const [savingConfig, setSavingConfig] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [discoveryFilter, setDiscoveryFilter] = useState<string>('all')
  const [jobActionLoading, setJobActionLoading] = useState<Record<string, boolean>>({})
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Trigger modal state
  const [showTriggerModal, setShowTriggerModal] = useState(false)
  const [triggerJobId, setTriggerJobId] = useState('')
  const [triggerUrl, setTriggerUrl] = useState('')
  const [triggerCompany, setTriggerCompany] = useState('')
  const [triggerTitle, setTriggerTitle] = useState('')
  const [triggering, setTriggering] = useState(false)

  // Selected run detail modal
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null)

  // Intervention form state
  const [interventionValue, setInterventionValue] = useState('')
  const [rememberScenario, setRememberScenario] = useState(true)
  const [submittingIntervention, setSubmittingIntervention] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [runsData, scenariosData, profileData, settingsData, jobsResponse, searchCfg, discJobs, resumesData] = await Promise.all([
        getAutomationRuns(),
        getAutomationScenarios(),
        getCandidateProfile(),
        getAutomationSettings(),
        api.get<Job[]>('/jobs'),
        getJobSearchConfig().catch(() => null),
        getDiscoveredJobs().catch(() => []),
        getResumes().catch(() => []),
      ])
      setRuns(runsData)
      setScenarios(scenariosData)
      setProfile(profileData)
      setSettings(settingsData)
      setSavedJobs(jobsResponse.data)
      setSearchConfig(searchCfg)
      setDiscoveredJobs(discJobs)
      setResumes(resumesData)

      if (searchCfg) {
        setDesiredJobTitle(searchCfg.desired_job_title || '')
        setDesiredLocation(searchCfg.desired_location || '')
        setYearsOfExp(searchCfg.years_of_experience ?? 3)
        setPlatformSearchUrl(searchCfg.platform_search_url || '')
        setSpecificCompany(searchCfg.specific_company || '')
        setSelectedResumeId(searchCfg.active_resume_id || '')
        setMaxJobs(searchCfg.max_jobs_to_discover ?? 10)
        setMinMatchScore(searchCfg.min_match_score ?? 60)
        setSkipAlreadyApplied(searchCfg.skip_already_applied ?? true)
        setScheduleInterval(searchCfg.schedule_interval || 'manual')
      } else if (resumesData.length > 0) {
        const active = resumesData.find((r) => r.is_active) || resumesData[0]
        setSelectedResumeId(active.id)
      }
    } catch {
      setError('Could not load automation data. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  function handleCopyUrl(url: string) {
    navigator.clipboard.writeText(url)
    setCopiedUrl(url)
    setTimeout(() => setCopiedUrl(null), 2500)
  }

  async function handleSaveSearchConfig(e?: FormEvent) {
    if (e) e.preventDefault()
    setSavingConfig(true)
    setError('')
    try {
      const saved = await saveJobSearchConfig({
        desired_job_title: desiredJobTitle,
        desired_location: desiredLocation,
        years_of_experience: Number(yearsOfExp),
        platform_search_url: platformSearchUrl,
        specific_company: specificCompany || undefined,
        active_resume_id: selectedResumeId || undefined,
        max_jobs_to_discover: Number(maxJobs),
        min_match_score: Number(minMatchScore),
        skip_already_applied: Boolean(skipAlreadyApplied),
        schedule_interval: scheduleInterval,
      })
      setSearchConfig(saved)
      setSuccessMsg('Job search configuration saved successfully.')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to save job search configuration.')
    } finally {
      setSavingConfig(false)
    }
  }

  async function handleTriggerDiscovery() {
    if (!desiredJobTitle || !desiredLocation || !platformSearchUrl) {
      setError('Please provide Desired Job Title, Location, and Platform Search URL.')
      return
    }
    setDiscovering(true)
    setError('')
    try {
      const cfg = await saveJobSearchConfig({
        desired_job_title: desiredJobTitle,
        desired_location: desiredLocation,
        years_of_experience: Number(yearsOfExp),
        platform_search_url: platformSearchUrl,
        specific_company: specificCompany || undefined,
        active_resume_id: selectedResumeId || undefined,
        max_jobs_to_discover: Number(maxJobs),
        min_match_score: Number(minMatchScore),
        skip_already_applied: Boolean(skipAlreadyApplied),
        schedule_interval: scheduleInterval,
      })
      setSearchConfig(cfg)

      const result = await triggerJobDiscovery({
        config_id: cfg.id,
        search_url: cfg.platform_search_url,
        max_results: cfg.max_jobs_to_discover,
        min_match_score: Number(minMatchScore),
        skip_already_applied: Boolean(skipAlreadyApplied),
      })

      const refreshed = await getDiscoveredJobs()
      setDiscoveredJobs(refreshed)
      setSuccessMsg(`Discovered ${result.total_discovered} jobs. ${result.total_matched} match your criteria.`)
      setTimeout(() => setSuccessMsg(''), 5000)
    } catch {
      setError('Job discovery encountered an issue. Ensure platform search URL is valid.')
    } finally {
      setDiscovering(false)
    }
  }

  async function handleQueueJob(jobId: string) {
    setJobActionLoading((prev) => ({ ...prev, [jobId]: true }))
    try {
      const updated = await queueDiscoveredJob(jobId)
      setDiscoveredJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)))
      setSuccessMsg(`Job candidate "${updated.exact_title}" queued.`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to queue job.')
    } finally {
      setJobActionLoading((prev) => ({ ...prev, [jobId]: false }))
    }
  }

  async function handleApplyJob(jobId: string) {
    setJobActionLoading((prev) => ({ ...prev, [jobId]: true }))
    try {
      const newRun = await applyDiscoveredJob(jobId)
      setRuns((prev) => [newRun, ...prev])
      const refreshed = await getDiscoveredJobs()
      setDiscoveredJobs(refreshed)
      setSuccessMsg(`Application launched for "${newRun.company} - ${newRun.job_title}". Locked exact job identity.`)
      setTimeout(() => setSuccessMsg(''), 5000)
    } catch {
      setError('Failed to launch application for this job.')
    } finally {
      setJobActionLoading((prev) => ({ ...prev, [jobId]: false }))
    }
  }

  async function handleTriggerSubmit(e: FormEvent) {
    e.preventDefault()
    setTriggering(true)
    setError('')
    try {
      const newRun = await triggerAutomationRun({
        job_id: triggerJobId || undefined,
        job_url: triggerUrl || undefined,
        company: triggerCompany || undefined,
        job_title: triggerTitle || undefined,
      })
      setRuns((current) => [newRun, ...current])
      setShowTriggerModal(false)
      setTriggerJobId('')
      setTriggerUrl('')
      setTriggerCompany('')
      setTriggerTitle('')
      setSuccessMsg(`Automation queued for ${newRun.company} - ${newRun.job_title}`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to trigger automation run. Check that a valid job URL was provided.')
    } finally {
      setTriggering(false)
    }
  }

  async function handlePause(runId: string) {
    try {
      const updated = await pauseAutomationRun(runId)
      setRuns((current) => current.map((r) => (r.id === updated.id ? updated : r)))
    } catch {
      setError('Could not pause automation run.')
    }
  }

  async function handleResume(runId: string) {
    try {
      const updated = await resumeAutomationRun(runId)
      setRuns((current) => current.map((r) => (r.id === updated.id ? updated : r)))
    } catch {
      setError('Could not resume automation run.')
    }
  }

  async function viewRunDetail(runId: string) {
    try {
      const detail = await getAutomationRun(runId)
      setSelectedRun(detail)
    } catch {
      setError('Could not load run details.')
    }
  }

  async function handleIntervene(run: AutomationRun, action: string) {
    setSubmittingIntervention(true)
    setError('')
    try {
      const val = action === 'approve' ? getSuggestedValue(run) : interventionValue
      const updated = await interveneAutomationRun(run.id, action, val, rememberScenario)
      setRuns((current) => current.map((r) => (r.id === updated.id ? updated : r)))
      setInterventionValue('')
      setSuccessMsg(`Intervention submitted (${action}). Automation will resume.`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to submit user intervention.')
    } finally {
      setSubmittingIntervention(false)
    }
  }

  async function handleProfileSave(e: FormEvent) {
    e.preventDefault()
    if (!profile) return
    setError('')
    try {
      const saved = await updateCandidateProfile(profile)
      setProfile(saved)
      setSuccessMsg('Candidate application profile saved successfully.')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to save profile changes.')
    }
  }

  async function handleSettingsSave(e: FormEvent) {
    e.preventDefault()
    if (!settings) return
    setError('')
    try {
      const saved = await updateAutomationSettings(settings)
      setSettings(saved)
      setSuccessMsg('Automation settings updated.')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setError('Failed to save automation settings.')
    }
  }

  async function handleToggleScenario(scenario: AutomationScenario) {
    try {
      const updated = await updateAutomationScenario(scenario.id, { is_active: !scenario.is_active })
      setScenarios((current) => current.map((s) => (s.id === updated.id ? updated : s)))
    } catch {
      setError('Could not update scenario.')
    }
  }

  async function handleDeleteScenario(id: string) {
    if (!window.confirm('Delete this learned scenario?')) return
    try {
      await deleteAutomationScenario(id)
      setScenarios((current) => current.filter((s) => s.id !== id))
    } catch {
      setError('Could not delete scenario.')
    }
  }

  const waitingRuns = runs.filter((r) => r.requires_user_action || r.status === 'WAITING_FOR_USER')
  const activeRuns = runs.filter((r) => ['APPLICATION_STARTED', 'FORM_IN_PROGRESS', 'AI_RESOLUTION', 'UNKNOWN_SCENARIO'].includes(r.status))
  const completedRuns = runs.filter((r) => ['SUBMITTED', 'FORM_COMPLETED'].includes(r.status))
  const pausedRuns = runs.filter((r) => r.status === 'PAUSED')

  function getSuggestedValue(run: AutomationRun): string {
    if (!run.suggested_action_json) return ''
    try {
      const parsed = JSON.parse(run.suggested_action_json)
      return parsed.target_value || ''
    } catch {
      return ''
    }
  }

  function getContextData(run: AutomationRun): Record<string, unknown> {
    if (!run.user_prompt_context_json) return {}
    try {
      return JSON.parse(run.user_prompt_context_json)
    } catch {
      return {}
    }
  }

  return (
    <main className="automation-page p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="automation-heading flex justify-between items-center mb-6">
        <div>
          <p className="page-kicker text-indigo-600 font-semibold text-sm">Agentic Workflow</p>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Application Automation</h1>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Autonomous job application engine with resilient Playwright automation, company adapters, and safe human-in-the-loop oversight.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            className="button button-small flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition"
            onClick={() => setShowTriggerModal(true)}
          >
            <Icon name="play" /> Run Automation
          </button>
          <button
            className="button button-small bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-3 py-2 rounded-lg hover:bg-gray-200 transition"
            onClick={loadData}
            title="Refresh Data"
          >
            <Icon name="refresh" />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6" role="alert">
          <strong>Error: </strong> {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 text-emerald-700 dark:text-emerald-300 px-4 py-3 rounded-lg mb-6">
          {successMsg}
        </div>
      )}

      {/* Stats Counter Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4 rounded-xl shadow-sm">
          <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">Active</span>
          <p className="text-2xl font-bold text-indigo-600 mt-1">{activeRuns.length}</p>
        </div>
        <div className={`p-4 rounded-xl border shadow-sm ${waitingRuns.length > 0 ? 'bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700' : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800'}`}>
          <span className="text-xs text-amber-700 dark:text-amber-400 font-medium uppercase tracking-wider flex items-center gap-1">
            {waitingRuns.length > 0 && <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />} Needs Input
          </span>
          <p className="text-2xl font-bold text-amber-600 mt-1">{waitingRuns.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4 rounded-xl shadow-sm">
          <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">Submitted</span>
          <p className="text-2xl font-bold text-emerald-600 mt-1">{completedRuns.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4 rounded-xl shadow-sm">
          <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">Paused</span>
          <p className="text-2xl font-bold text-gray-600 mt-1">{pausedRuns.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4 rounded-xl shadow-sm">
          <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">Learned Scenarios</span>
          <p className="text-2xl font-bold text-purple-600 mt-1">{scenarios.length}</p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-gray-200 dark:border-gray-800 mb-6 gap-2">
        <button
          className={`pb-3 px-4 font-medium text-sm flex items-center gap-2 border-b-2 transition ${activeTab === 'runs' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('runs')}
        >
          <Icon name="play" /> Runs & Status
        </button>
        <button
          className={`pb-3 px-4 font-medium text-sm flex items-center gap-2 border-b-2 transition ${activeTab === 'search' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('search')}
        >
          <Icon name="search" /> Job Search
          {discoveredJobs.length > 0 && (
            <span className="bg-indigo-100 text-indigo-800 text-xs px-2 py-0.5 rounded-full font-bold">
              {discoveredJobs.length}
            </span>
          )}
        </button>
        <button
          className={`pb-3 px-4 font-medium text-sm flex items-center gap-2 border-b-2 transition ${activeTab === 'interventions' ? 'border-amber-500 text-amber-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('interventions')}
        >
          <Icon name="spark" /> Human Intervention
          {waitingRuns.length > 0 && (
            <span className="bg-amber-500 text-white text-xs px-2 py-0.5 rounded-full font-bold">
              {waitingRuns.length}
            </span>
          )}
        </button>
        <button
          className={`pb-3 px-4 font-medium text-sm flex items-center gap-2 border-b-2 transition ${activeTab === 'memory' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('memory')}
        >
          <Icon name="book" /> Scenario Memory
        </button>
        <button
          className={`pb-3 px-4 font-medium text-sm flex items-center gap-2 border-b-2 transition ${activeTab === 'settings' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('settings')}
        >
          <Icon name="grid" /> Profile & Settings
        </button>
      </div>

      {/* TAB 1: RUNS & PIPELINE */}
      {activeTab === 'runs' && (
        <section className="runs-section">
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading automation runs...</div>
          ) : runs.length === 0 ? (
            <div className="bg-white dark:bg-gray-900 border border-dashed border-gray-300 dark:border-gray-800 rounded-xl p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 flex items-center justify-center mx-auto mb-3">
                <Icon name="play" />
              </div>
              <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">No automation runs yet</h2>
              <p className="text-sm text-gray-500 max-w-md mx-auto mt-1 mb-4">
                Select a saved job with an application URL or paste a career posting link to start autonomous application filing.
              </p>
              <button
                className="button button-small bg-indigo-600 text-white px-4 py-2 rounded-lg"
                onClick={() => setShowTriggerModal(true)}
              >
                Start First Application
              </button>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-800 text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Company & Role</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Current Step</th>
                    <th className="px-4 py-3">Scenarios Used</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                  {runs.map((run) => (
                    <tr key={run.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition">
                      <td className="px-4 py-3">
                        <strong className="block text-gray-900 dark:text-white">{run.company}</strong>
                        <span className="text-xs text-gray-500">{run.job_title}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 text-xs rounded-full font-semibold ${
                            run.status === 'SUBMITTED'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                              : run.status === 'WAITING_FOR_USER'
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                                : run.status === 'FAILED'
                                  ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
                                  : run.status === 'PAUSED'
                                    ? 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                                    : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300'
                          }`}
                        >
                          {run.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-300 text-xs">
                        {run.current_step || '-'}
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-300 text-xs">
                        {run.scenarios_used_count}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(run.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            className="text-indigo-600 hover:underline text-xs"
                            onClick={() => viewRunDetail(run.id)}
                          >
                            Logs
                          </button>
                          {run.status === 'PAUSED' && (
                            <button
                              className="text-emerald-600 hover:underline text-xs"
                              onClick={() => handleResume(run.id)}
                            >
                              Resume
                            </button>
                          )}
                          {['APPLICATION_STARTED', 'FORM_IN_PROGRESS'].includes(run.status) && (
                            <button
                              className="text-amber-600 hover:underline text-xs"
                              onClick={() => handlePause(run.id)}
                            >
                              Pause
                            </button>
                          )}
                          {run.status === 'WAITING_FOR_USER' && (
                            <button
                              className="text-amber-600 font-semibold hover:underline text-xs"
                              onClick={() => setActiveTab('interventions')}
                            >
                              Review &rarr;
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* TAB: JOB SEARCH & MULTI-JOB DISCOVERY */}
      {activeTab === 'search' && (
        <section className="job-search-section space-y-6">
          {/* Configuration Card */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 mb-6 border-b border-gray-200 dark:border-gray-800 gap-3">
              <div>
                <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <Icon name="search" /> Job Search & Multi-Job Discovery
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  Configure target search criteria, discover job openings across configured platforms, and score candidate compatibility.
                  {searchConfig?.id && (
                    <span className="ml-2 text-indigo-600 dark:text-indigo-400 font-medium">
                      (Config saved)
                    </span>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={savingConfig}
                  onClick={handleSaveSearchConfig}
                  className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition border border-gray-300 dark:border-gray-700"
                >
                  {savingConfig ? 'Saving...' : 'Save Configuration'}
                </button>
                <button
                  type="button"
                  disabled={discovering || !desiredJobTitle || !desiredLocation || !platformSearchUrl}
                  onClick={handleTriggerDiscovery}
                  className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition shadow-sm disabled:opacity-50 flex items-center gap-1.5"
                >
                  {discovering ? (
                    <>
                      <Icon name="refresh" className="animate-spin" /> Discovering...
                    </>
                  ) : (
                    <>
                      <Icon name="search" /> Discover Jobs
                    </>
                  )}
                </button>
              </div>
            </div>

            <form onSubmit={handleSaveSearchConfig} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Desired Job Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Software Developer"
                  value={desiredJobTitle}
                  onChange={(e) => setDesiredJobTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">Flexible title matching with canonical normalization</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Desired Location <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Bangalore, Remote, San Francisco"
                  value={desiredLocation}
                  onChange={(e) => setDesiredLocation(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">Supports metro clusters (e.g. Bengaluru, Bay Area, Remote)</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Years of Work Experience <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  required
                  min={0}
                  max={50}
                  step={0.5}
                  placeholder="3"
                  value={yearsOfExp}
                  onChange={(e) => setYearsOfExp(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">Used for 20% experience range compatibility scoring</span>
              </div>

              <div className="lg:col-span-2">
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Platform / Job Search URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="url"
                  required
                  placeholder="e.g. https://www.naukri.com/software-developer-jobs-in-bangalore or search results page"
                  value={platformSearchUrl}
                  onChange={(e) => setPlatformSearchUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-xs"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">URL where multi-job listings are scraped and candidate links are extracted</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Specific Company <span className="text-gray-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Google, Amazon, Stripe"
                  value={specificCompany}
                  onChange={(e) => setSpecificCompany(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">Filter discovery strictly or prioritize target company</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Active Resume for Skills Matching
                </label>
                <select
                  value={selectedResumeId}
                  onChange={(e) => setSelectedResumeId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                >
                  <option value="">-- Select Active Resume --</option>
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.filename} {r.is_active ? '(Active)' : ''}
                    </option>
                  ))}
                </select>
                <span className="text-[11px] text-gray-500 mt-0.5 block">Skills from resume used for 25% skill overlap scoring</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Max Jobs to Discover
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={maxJobs}
                  onChange={(e) => setMaxJobs(parseInt(e.target.value) || 10)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <span className="text-[11px] text-gray-500 mt-0.5 block">Default: 10 job candidates</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Min Match Score ({minMatchScore}%)
                </label>
                <input
                  type="range"
                  min={20}
                  max={95}
                  step={5}
                  value={minMatchScore}
                  onChange={(e) => setMinMatchScore(parseInt(e.target.value) || 60)}
                  className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                />
                <div className="flex justify-between text-[11px] text-gray-500 mt-1">
                  <span>20% (Loose)</span>
                  <span className="font-bold text-indigo-600 dark:text-indigo-400">{minMatchScore}%</span>
                  <span>95% (Strict)</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Schedule Interval
                </label>
                <select
                  value={scheduleInterval}
                  onChange={(e) => setScheduleInterval(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                >
                  <option value="manual">Manual Only</option>
                  <option value="hourly">Every Hour</option>
                  <option value="4h">Every 4 Hours</option>
                  <option value="daily">Daily</option>
                </select>
                <span className="text-[11px] text-gray-500 mt-0.5 block">Periodic automated background search</span>
              </div>

              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="skip-already-applied"
                  checked={skipAlreadyApplied}
                  onChange={(e) => setSkipAlreadyApplied(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                />
                <label htmlFor="skip-already-applied" className="text-xs font-bold text-gray-800 dark:text-gray-200 cursor-pointer">
                  Skip Already Applied Postings
                </label>
              </div>
            </form>
          </div>

          {/* Discovery Results Section */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-4 border-b border-gray-200 dark:border-gray-800 gap-3">
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Discovered Job Candidates ({discoveredJobs.length})
                </h3>
                <p className="text-xs text-gray-500">
                  Ranked by composite match score (Title 40%, Skills 25%, Experience 20%, Location 15%).
                </p>
              </div>

              {/* Status Filter Buttons */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                {['all', 'DISCOVERED', 'QUEUED', 'APPLYING', 'APPLIED'].map((filterVal) => (
                  <button
                    key={filterVal}
                    type="button"
                    onClick={() => setDiscoveryFilter(filterVal)}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                      discoveryFilter === filterVal
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    {filterVal === 'all' ? 'All' : filterVal}
                  </button>
                ))}
              </div>
            </div>

            {discoveredJobs.length === 0 ? (
              <div className="p-12 text-center border border-dashed border-gray-200 dark:border-gray-800 rounded-xl">
                <div className="w-12 h-12 rounded-full bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 flex items-center justify-center mx-auto mb-2">
                  <Icon name="search" />
                </div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white">No jobs discovered yet</h4>
                <p className="text-xs text-gray-500 max-w-sm mx-auto mt-1">
                  Configure your search preferences above and click &quot;Discover Jobs&quot; to fetch candidate openings.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {discoveredJobs
                  .filter((job) => discoveryFilter === 'all' || job.status.toUpperCase() === discoveryFilter.toUpperCase())
                  .map((job) => {
                    let reasons: string[] = []
                    try {
                      if (job.match_reasons_json) {
                        reasons = JSON.parse(job.match_reasons_json)
                      }
                    } catch {}

                    let breakdown: any = {}
                    try {
                      if (job.match_breakdown_json) {
                        breakdown = JSON.parse(job.match_breakdown_json)
                      }
                    } catch {}

                    const score = job.match_score ?? 0
                    const scoreColor =
                      score >= 80
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                        : score >= 60
                          ? 'bg-amber-50 text-amber-700 border-amber-300'
                          : 'bg-rose-50 text-rose-700 border-rose-300'

                    return (
                      <div
                        key={job.id}
                        className="border border-gray-200 dark:border-gray-800 rounded-xl p-5 hover:border-indigo-200 dark:hover:border-indigo-900 transition bg-white dark:bg-gray-900 shadow-sm"
                      >
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${scoreColor}`}>
                                {score.toFixed(0)}% Match
                              </span>
                              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 uppercase font-semibold">
                                {job.platform}
                              </span>
                              <span className="text-xs px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-semibold">
                                {job.status}
                              </span>
                              {job.requisition_id && (
                                <span className="text-xs px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 font-mono font-semibold border border-amber-200 dark:border-amber-800">
                                  Req: {job.requisition_id}
                                </span>
                              )}
                            </div>

                            <h4 className="text-base font-bold text-gray-900 dark:text-white truncate">
                              {job.exact_title}
                            </h4>
                            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mt-0.5">
                              {job.company} &bull; <span className="text-gray-500">{job.location || 'Location Unspecified'}</span>
                              {job.experience_raw && (
                                <span className="ml-2 text-indigo-600 dark:text-indigo-400 font-medium">
                                  &bull; Exp: {job.experience_raw}
                                </span>
                              )}
                            </p>

                            {/* Score Breakdown Pills */}
                            <div className="flex flex-wrap gap-2 mt-3 text-[11px]">
                              <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">
                                Title: <strong className="text-gray-900 dark:text-white">{breakdown.title_score ?? 0}%</strong> (40%)
                              </span>
                              <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">
                                Skills: <strong className="text-gray-900 dark:text-white">{breakdown.skills_score ?? 0}%</strong> (25%)
                              </span>
                              <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">
                                Exp: <strong className="text-gray-900 dark:text-white">{breakdown.experience_score ?? 0}%</strong> (20%)
                              </span>
                              <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">
                                Location: <strong className="text-gray-900 dark:text-white">{breakdown.location_score ?? 0}%</strong> (15%)
                              </span>
                            </div>

                            {/* Matched & Missing Skills */}
                            {(() => {
                              let matchedSkills: string[] = job.matched_skills || []
                              let missingSkills: string[] = job.missing_skills || []
                              try {
                                if (!matchedSkills.length && job.matched_skills_json) {
                                  matchedSkills = JSON.parse(job.matched_skills_json)
                                }
                              } catch {}
                              try {
                                if (!missingSkills.length && job.missing_skills_json) {
                                  missingSkills = JSON.parse(job.missing_skills_json)
                                }
                              } catch {}

                              if (!matchedSkills.length && !missingSkills.length) return null

                              return (
                                <div className="mt-3 space-y-1.5">
                                  {matchedSkills.length > 0 && (
                                    <div className="flex flex-wrap items-center gap-1.5">
                                      <span className="text-[11px] font-bold text-emerald-800 dark:text-emerald-400">
                                        Matched Skills:
                                      </span>
                                      {matchedSkills.map((s, idx) => (
                                        <span
                                          key={idx}
                                          className="bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 text-[10px] font-semibold px-2 py-0.5 rounded-md"
                                        >
                                          {s}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  {missingSkills.length > 0 && (
                                    <div className="flex flex-wrap items-center gap-1.5">
                                      <span className="text-[11px] font-bold text-amber-800 dark:text-amber-400">
                                        Missing Skills:
                                      </span>
                                      {missingSkills.slice(0, 6).map((s, idx) => (
                                        <span
                                          key={idx}
                                          className="bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 text-[10px] font-semibold px-2 py-0.5 rounded-md"
                                        >
                                          {s}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )
                            })()}

                            {/* Reasoning */}
                            {reasons.length > 0 && (
                              <div className="mt-2.5 space-y-1">
                                {reasons.slice(0, 3).map((r, i) => (
                                  <p key={i} className="text-[11px] text-gray-600 dark:text-gray-400 flex items-center gap-1.5">
                                    <span className="text-emerald-500 font-bold">&check;</span> {r}
                                  </p>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Action Buttons */}
                          <div className="flex flex-row md:flex-col gap-2 shrink-0 items-end">
                            <a
                              href={job.job_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-3 py-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 rounded border border-indigo-200 transition"
                            >
                              Open Job &rarr;
                            </a>

                            {job.status === 'DISCOVERED' && (
                              <button
                                type="button"
                                disabled={jobActionLoading[job.id]}
                                onClick={() => handleQueueJob(job.id)}
                                className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-800 rounded border border-gray-300 transition disabled:opacity-50"
                              >
                                {jobActionLoading[job.id] ? 'Queueing...' : 'Queue Job'}
                              </button>
                            )}

                            {job.status !== 'APPLIED' && job.status !== 'APPLYING' && (
                              <button
                                type="button"
                                disabled={jobActionLoading[job.id]}
                                onClick={() => handleApplyJob(job.id)}
                                className="px-3 py-1.5 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded shadow-sm transition disabled:opacity-50"
                              >
                                {jobActionLoading[job.id] ? 'Launching...' : 'Apply Now'}
                              </button>
                            )}

                            {job.status === 'APPLIED' && (
                              <span className="text-xs font-bold text-emerald-600 px-3 py-1">
                                &check; Applied
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
              </div>
            )}
          </div>
        </section>
      )}

      {/* TAB 2: HUMAN INTERVENTION PANEL */}
      {activeTab === 'interventions' && (
        <section className="interventions-section">
          {waitingRuns.length === 0 ? (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center mx-auto mb-2">
                <Icon name="checkCircle" />
              </div>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">All runs clear</h2>
              <p className="text-xs text-gray-500 mt-1">
                No active applications currently require human input or safety clarification.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {waitingRuns.map((run) => {
                const ctx = getContextData(run)
                const suggested = getSuggestedValue(run)
                const isRealTrackedUrl =
                  Boolean(run.current_url) &&
                  !run.current_url!.includes('about:blank') &&
                  (run.current_url!.startsWith('http://') || run.current_url!.startsWith('https://'))

                return (
                  <div
                    key={run.id}
                    className="bg-[#fcfaf6] border-2 border-amber-300/90 rounded-xl p-6 shadow-md"
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4 border-b border-amber-200 pb-3">
                      <div>
                        <span className="text-xs font-extrabold uppercase tracking-wider text-amber-900">
                          Human Input Required
                        </span>
                        <h3 className="text-xl font-black text-gray-950 mt-0.5">
                          {run.company} &mdash; {run.job_title}
                        </h3>
                      </div>
                      <span className="text-xs font-bold text-amber-950 bg-amber-100/90 border border-amber-300 px-2.5 py-1 rounded-md">
                        Step: {run.current_step || 'Submission Review'}
                      </span>
                    </div>

                    {/* CURRENT PAGE / URL TRACKING CARD */}
                    <div className="bg-white border border-amber-300/80 rounded-lg p-4 mb-5 shadow-sm">
                      <div className="flex items-center justify-between mb-3 pb-2 border-b border-amber-100">
                        <span className="text-xs font-bold uppercase tracking-wider text-gray-800 flex items-center gap-1.5">
                          <Icon name="link" /> Current Page
                        </span>
                        {isRealTrackedUrl ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-900 border border-emerald-300">
                            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
                            Live URL Tracked
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300">
                            Initial Navigation
                          </span>
                        )}
                      </div>

                      <div className="space-y-3 text-xs">
                        <div>
                          <span className="font-bold text-gray-900 block mb-1">URL:</span>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-xs font-medium text-gray-900 bg-gray-50 border border-gray-300 px-2.5 py-1.5 rounded select-all break-all flex-1 min-w-[200px]">
                              {isRealTrackedUrl ? run.current_url : (run.job_url || 'Navigation starting...')}
                            </span>
                            {isRealTrackedUrl && (
                              <button
                                type="button"
                                onClick={() => handleCopyUrl(run.current_url!)}
                                className="px-3 py-1.5 text-xs font-bold bg-gray-100 hover:bg-gray-200 text-gray-900 rounded border border-gray-400 transition shrink-0 shadow-sm"
                              >
                                {copiedUrl === run.current_url ? 'Copied!' : 'Copy URL'}
                              </button>
                            )}
                            {isRealTrackedUrl && (
                              <a
                                href={run.current_url!}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 text-xs font-bold bg-indigo-50 hover:bg-indigo-100 text-indigo-800 rounded border border-indigo-300 transition shrink-0 shadow-sm"
                              >
                                Open Current Page &rarr;
                              </a>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                          <div>
                            <span className="font-bold text-gray-900 block mb-0.5">PAGE TITLE:</span>
                            <p className="font-semibold text-gray-900 bg-gray-50 border border-gray-300 px-2.5 py-1.5 rounded">
                              {run.page_title || run.job_title || 'Application Portal Page'}
                            </p>
                          </div>
                          <div>
                            <span className="font-bold text-gray-900 block mb-0.5">STEP:</span>
                            <p className="font-semibold text-gray-900 bg-gray-50 border border-gray-300 px-2.5 py-1.5 rounded">
                              {run.current_step || 'Submission Review'}
                            </p>
                          </div>
                        </div>

                        {Boolean(ctx.confidence_reason) && (
                          <div className="pt-1">
                            <span className="font-bold text-gray-900 block mb-0.5">REASON:</span>
                            <p className="font-medium text-amber-950 bg-amber-50/80 border border-amber-200 px-2.5 py-1.5 rounded">
                              {String(ctx.confidence_reason)}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Prompt Box */}
                    <div className="bg-amber-100/80 border border-amber-300 rounded-lg p-4 mb-4 shadow-sm">
                      <p className="text-base font-bold text-gray-950 leading-snug">
                        {run.user_prompt || 'Form completed! Please review and approve final application submission.'}
                      </p>
                    </div>

                    {suggested && (
                      <div className="bg-white border border-indigo-200 rounded-lg p-3.5 mb-4 text-xs shadow-sm">
                        <span className="font-bold text-gray-900 text-sm">Suggested Action / Value: </span>
                        <code className="text-indigo-900 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded font-mono font-bold text-sm ml-1">
                          {suggested}
                        </code>
                      </div>
                    )}

                    {/* Answer Input */}
                    <div className="mb-4">
                      <label className="block text-sm font-bold text-gray-950 mb-1.5">
                        Your answer or customized value:
                      </label>
                      <input
                        type="text"
                        className="w-full px-3.5 py-2.5 border-2 border-gray-300 focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600 rounded-lg text-sm bg-white text-gray-950 font-semibold placeholder:text-gray-500 shadow-sm"
                        placeholder={suggested || 'Type your manual answer here...'}
                        value={interventionValue}
                        onChange={(e) => setInterventionValue(e.target.value)}
                      />
                    </div>

                    {/* Remember Checkbox */}
                    <div className="flex items-center gap-2.5 mb-5 bg-white/70 border border-amber-200 p-2.5 rounded-lg">
                      <input
                        type="checkbox"
                        id={`remember-${run.id}`}
                        checked={rememberScenario}
                        onChange={(e) => setRememberScenario(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-400 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                      <label htmlFor={`remember-${run.id}`} className="text-sm font-bold text-gray-950 cursor-pointer select-none">
                        Remember this answer in Scenario Memory for future runs
                      </label>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap gap-2.5">
                      {suggested && (
                        <button
                          disabled={submittingIntervention}
                          onClick={() => handleIntervene(run, 'approve')}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition shadow-sm"
                        >
                          Approve Suggested
                        </button>
                      )}
                      <button
                        disabled={submittingIntervention || !interventionValue.trim()}
                        onClick={() => handleIntervene(run, 'edit')}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition disabled:opacity-50 shadow-sm"
                      >
                        Submit Answer
                      </button>
                      <button
                        disabled={submittingIntervention}
                        onClick={() => handleIntervene(run, 'pause')}
                        className="bg-gray-200 hover:bg-gray-300 text-gray-900 text-xs font-bold px-4 py-2.5 rounded-lg transition border border-gray-300"
                      >
                        Pause
                      </button>
                      <button
                        disabled={submittingIntervention}
                        onClick={() => handleIntervene(run, 'reject')}
                        className="bg-red-100 hover:bg-red-200 text-red-900 text-xs font-bold px-4 py-2.5 rounded-lg transition border border-red-300"
                      >
                        Reject & Stop
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      )}

      {/* TAB 3: SCENARIO MEMORY */}
      {activeTab === 'memory' && (
        <section className="memory-section">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
              <div>
                <h2 className="text-base font-bold text-gray-900 dark:text-white">Learned Interaction Handlers</h2>
                <p className="text-xs text-gray-500">
                  CareerPilot automatically remembers successfully resolved application scenarios to self-heal without writing code.
                </p>
              </div>
              <span className="text-xs text-gray-400">{scenarios.length} stored</span>
            </div>

            {scenarios.length === 0 ? (
              <div className="p-8 text-center text-gray-500 text-sm">
                No custom scenarios learned yet. As you approve form questions, they will appear here.
              </div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-800 text-gray-500 text-xs">
                  <tr>
                    <th className="px-4 py-3">Company</th>
                    <th className="px-4 py-3">Field Key</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Value Source / Value</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3">Times Used</th>
                    <th className="px-4 py-3 text-right">Enabled</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 text-xs">
                  {scenarios.map((scen) => (
                    <tr key={scen.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition">
                      <td className="px-4 py-3 font-semibold">{scen.company === '*' ? 'Universal' : scen.company}</td>
                      <td className="px-4 py-3 font-mono">{scen.field_key}</td>
                      <td className="px-4 py-3 uppercase">{scen.action_type}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                        {scen.static_value || scen.value_source}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                          {scen.confidence}
                        </span>
                      </td>
                      <td className="px-4 py-3">{scen.times_used}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end items-center gap-2">
                          <button
                            onClick={() => handleToggleScenario(scen)}
                            className={`px-2 py-1 rounded text-xs font-medium ${scen.is_active ? 'bg-indigo-50 text-indigo-700' : 'bg-gray-100 text-gray-400'}`}
                          >
                            {scen.is_active ? 'Active' : 'Disabled'}
                          </button>
                          <button
                            onClick={() => handleDeleteScenario(scen.id)}
                            className="text-red-500 hover:text-red-700 px-1"
                            title="Delete scenario"
                          >
                            &times;
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* TAB 4: CANDIDATE PROFILE & SETTINGS */}
      {activeTab === 'settings' && (
        <section className="settings-section grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Candidate Profile Form */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-gray-900 dark:text-white mb-1">Normalized Application Profile</h2>
            <p className="text-xs text-gray-500 mb-4">
              CareerPilot uses this verified information to fill application forms. Missing fields will prompt for user input instead of guessing.
            </p>

            {profile && (
              <form onSubmit={handleProfileSave} className="space-y-3 text-xs">
                <div>
                  <label className="block font-medium mb-1">Telephone / Mobile</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    placeholder="+1 (555) 019-2834"
                    value={profile.phone || ''}
                    onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1">Location (City, State / Country)</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    placeholder="San Francisco, CA"
                    value={profile.location || ''}
                    onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block font-medium mb-1">LinkedIn URL</label>
                    <input
                      type="url"
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                      placeholder="https://linkedin.com/in/..."
                      value={profile.linkedin_url || ''}
                      onChange={(e) => setProfile({ ...profile, linkedin_url: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block font-medium mb-1">GitHub URL</label>
                    <input
                      type="url"
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                      placeholder="https://github.com/..."
                      value={profile.github_url || ''}
                      onChange={(e) => setProfile({ ...profile, github_url: e.target.value })}
                    />
                  </div>
                </div>
                <div>
                  <label className="block font-medium mb-1">Work Authorization</label>
                  <select
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={profile.work_authorization || ''}
                    onChange={(e) => setProfile({ ...profile, work_authorization: e.target.value })}
                  >
                    <option value="">Select status...</option>
                    <option value="US Citizen">US Citizen</option>
                    <option value="Permanent Resident (Green Card)">Permanent Resident (Green Card)</option>
                    <option value="Authorized to work for any employer">Authorized to work for any employer</option>
                    <option value="Authorized on Visa">Authorized on Visa</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-1">Will you require visa sponsorship?</label>
                  <select
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={profile.requires_sponsorship === null ? '' : profile.requires_sponsorship ? 'yes' : 'no'}
                    onChange={(e) => {
                      const val = e.target.value === '' ? null : e.target.value === 'yes'
                      setProfile({ ...profile, requires_sponsorship: val })
                    }}
                  >
                    <option value="">Unspecified (Will ask user on each application)</option>
                    <option value="no">No, I do not require sponsorship</option>
                    <option value="yes">Yes, I require sponsorship</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block font-medium mb-1">Highest Degree</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                      placeholder="Bachelor of Science"
                      value={profile.education_degree || ''}
                      onChange={(e) => setProfile({ ...profile, education_degree: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block font-medium mb-1">School / University</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                      placeholder="UC Berkeley"
                      value={profile.education_school || ''}
                      onChange={(e) => setProfile({ ...profile, education_school: e.target.value })}
                    />
                  </div>
                </div>
                <div className="pt-2">
                  <button type="submit" className="button button-small bg-indigo-600 text-white px-4 py-2 rounded-lg">
                    Save Profile
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Automation & Scheduler Settings */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-gray-900 dark:text-white mb-1">Scheduler & Policy Settings</h2>
            <p className="text-xs text-gray-500 mb-4">
              Configure scheduled job checks, per-day application limits, and final submission safety.
            </p>

            {settings && (
              <form onSubmit={handleSettingsSave} className="space-y-4 text-xs">
                <div>
                  <label className="block font-medium mb-1">Automated Scheduler Interval</label>
                  <select
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={settings.schedule_interval}
                    onChange={(e) => setSettings({ ...settings, schedule_interval: e.target.value })}
                  >
                    <option value="manual">Manual Only (No background schedule)</option>
                    <option value="1h">Every Hour</option>
                    <option value="4h">Every 4 Hours</option>
                    <option value="daily">Daily (Once per 24 hours)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium mb-1">Maximum Applications Per Day (Rate Limit)</label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={settings.max_daily_applications}
                    onChange={(e) => setSettings({ ...settings, max_daily_applications: Number(e.target.value) })}
                  />
                </div>

                <div className="p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      id="auto-submit-pref"
                      checked={settings.auto_submit}
                      onChange={(e) => setSettings({ ...settings, auto_submit: e.target.checked })}
                      className="mt-0.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div>
                      <label htmlFor="auto-submit-pref" className="font-semibold text-gray-900 dark:text-white block">
                        Enable Automatic Final Submission
                      </label>
                      <span className="text-gray-500 text-xs block mt-0.5">
                        When disabled, automation completes all form fields and enters <strong>SUBMISSION_REVIEW</strong> for your final sign-off before submitting.
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <button type="submit" className="button button-small bg-indigo-600 text-white px-4 py-2 rounded-lg">
                    Save Settings
                  </button>
                </div>
              </form>
            )}
          </div>
        </section>
      )}

      {/* Trigger Modal */}
      {showTriggerModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl max-w-lg w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-2">Run Job Automation</h2>
            <p className="text-xs text-gray-500 mb-4">
              Select a saved job from your workspace or paste a direct career portal application URL.
            </p>

            <form onSubmit={handleTriggerSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium mb-1">Choose Saved Job (Optional)</label>
                <select
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  value={triggerJobId}
                  onChange={(e) => {
                    const id = e.target.value
                    setTriggerJobId(id)
                    const matched = savedJobs.find((j) => j.id === id)
                    if (matched) {
                      setTriggerCompany(matched.company)
                      setTriggerTitle(matched.title)
                      setTriggerUrl(matched.url || '')
                    }
                  }}
                >
                  <option value="">Or enter custom job details below...</option>
                  {savedJobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title} · {j.company} {j.url ? '🔗' : '(no URL)'}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-medium mb-1">Application URL (Required)</label>
                <input
                  type="url"
                  required
                  placeholder="https://company.com/careers/jobs/123"
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  value={triggerUrl}
                  onChange={(e) => setTriggerUrl(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1">Company Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Stripe"
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={triggerCompany}
                    onChange={(e) => setTriggerCompany(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1">Role Title</label>
                  <input
                    type="text"
                    required
                    placeholder="Backend Engineer"
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    value={triggerTitle}
                    onChange={(e) => setTriggerTitle(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setShowTriggerModal(false)}
                  className="px-4 py-2 text-xs font-medium text-gray-600 dark:text-gray-300 hover:underline"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={triggering}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-medium transition"
                >
                  {triggering ? 'Launching...' : 'Start Automation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Run Detail & Action Logs Modal */}
      {selectedRun && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl max-w-2xl w-full p-6 shadow-xl max-h-[85vh] flex flex-col">
            <div className="flex justify-between items-center mb-4 border-b border-gray-200 dark:border-gray-800 pb-3">
              <div>
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                  {selectedRun.company} — {selectedRun.job_title}
                </h2>
                <span className="text-xs text-gray-500">Status: {selectedRun.status} · Scenarios Used: {selectedRun.scenarios_used_count}</span>
              </div>
              <button onClick={() => setSelectedRun(null)} className="text-gray-400 hover:text-gray-600 text-xl font-bold">
                &times;
              </button>
            </div>

            <div className="overflow-y-auto flex-1 space-y-2 pr-1">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Detailed Action Logs</h3>
              {!selectedRun.action_logs || selectedRun.action_logs.length === 0 ? (
                <div className="text-xs text-gray-400 py-4 text-center">No action logs recorded yet.</div>
              ) : (
                selectedRun.action_logs.map((log) => (
                  <div key={log.id} className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-lg text-xs border border-gray-100 dark:border-gray-800">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-semibold text-gray-900 dark:text-white uppercase">{log.action_type}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${log.confidence === 'HIGH' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                        {log.confidence} ({log.action_source})
                      </span>
                    </div>
                    <p className="text-gray-600 dark:text-gray-400"><strong>Field:</strong> {log.step_name}</p>
                    <p className="text-gray-600 dark:text-gray-400"><strong>Value:</strong> {log.value_used || '(empty)'}</p>
                    {log.confidence_reason && (
                      <p className="text-gray-400 text-[11px] italic mt-1">{log.confidence_reason}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
