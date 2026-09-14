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
  api,
  type AutomationRun,
  type AutomationScenario,
  type AutomationSetting,
  type CandidateProfile,
  type Job,
} from '../lib/api'
import { Icon } from './Icon'

type TabType = 'runs' | 'interventions' | 'memory' | 'settings'

export function AutomationDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('runs')
  const [runs, setRuns] = useState<AutomationRun[]>([])
  const [scenarios, setScenarios] = useState<AutomationScenario[]>([])
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [settings, setSettings] = useState<AutomationSetting | null>(null)
  const [savedJobs, setSavedJobs] = useState<Job[]>([])

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
      const [runsData, scenariosData, profileData, settingsData, jobsResponse] = await Promise.all([
        getAutomationRuns(),
        getAutomationScenarios(),
        getCandidateProfile(),
        getAutomationSettings(),
        api.get<Job[]>('/jobs'),
      ])
      setRuns(runsData)
      setScenarios(scenariosData)
      setProfile(profileData)
      setSettings(settingsData)
      setSavedJobs(jobsResponse.data)
    } catch {
      setError('Could not load automation data. Ensure backend is running.')
    } finally {
      setLoading(false)
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
            <div className="space-y-4">
              {waitingRuns.map((run) => {
                const ctx = getContextData(run)
                const suggested = getSuggestedValue(run)
                return (
                  <div
                    key={run.id}
                    className="bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-4 border-b border-amber-200 dark:border-amber-800/60 pb-3">
                      <div>
                        <span className="text-xs font-semibold uppercase text-amber-700 dark:text-amber-400">
                          Human Input Required
                        </span>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white mt-0.5">
                          {run.company} — {run.job_title}
                        </h3>
                      </div>
                      <span className="text-xs text-gray-500">Step: {run.current_step || 'Application'}</span>
                    </div>

                    <div className="mb-4">
                      <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                        {run.user_prompt}
                      </p>
                      {typeof ctx.confidence_reason === 'string' && (
                        <p className="text-xs text-gray-500 italic mt-1">
                          Reason: {ctx.confidence_reason}
                        </p>
                      )}
                    </div>

                    {suggested && (
                      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3 mb-4 text-xs">
                        <span className="font-semibold text-gray-600 dark:text-gray-400">Suggested Action: </span>
                        <code className="text-indigo-600 dark:text-indigo-400 font-mono">{suggested}</code>
                      </div>
                    )}

                    <div className="mb-4">
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Your answer or customized value:
                      </label>
                      <input
                        type="text"
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                        placeholder={suggested || 'Type your manual answer here...'}
                        value={interventionValue}
                        onChange={(e) => setInterventionValue(e.target.value)}
                      />
                    </div>

                    <div className="flex items-center gap-2 mb-4">
                      <input
                        type="checkbox"
                        id={`remember-${run.id}`}
                        checked={rememberScenario}
                        onChange={(e) => setRememberScenario(e.target.checked)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <label htmlFor={`remember-${run.id}`} className="text-xs text-gray-600 dark:text-gray-400">
                        Remember this answer in Scenario Memory for future runs
                      </label>
                    </div>

                    <div className="flex gap-2">
                      {suggested && (
                        <button
                          disabled={submittingIntervention}
                          onClick={() => handleIntervene(run, 'approve')}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs px-4 py-2 rounded-lg font-medium transition"
                        >
                          Approve Suggested
                        </button>
                      )}
                      <button
                        disabled={submittingIntervention || !interventionValue.trim()}
                        onClick={() => handleIntervene(run, 'edit')}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-4 py-2 rounded-lg font-medium transition disabled:opacity-50"
                      >
                        Submit Answer
                      </button>
                      <button
                        disabled={submittingIntervention}
                        onClick={() => handleIntervene(run, 'pause')}
                        className="bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 text-gray-700 dark:text-gray-300 text-xs px-3 py-2 rounded-lg transition"
                      >
                        Pause
                      </button>
                      <button
                        disabled={submittingIntervention}
                        onClick={() => handleIntervene(run, 'reject')}
                        className="bg-red-50 text-red-600 hover:bg-red-100 text-xs px-3 py-2 rounded-lg transition"
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
