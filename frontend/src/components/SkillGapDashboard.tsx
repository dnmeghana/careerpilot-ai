import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type SkillGap } from '../lib/api'
import { Icon } from './Icon'

export function SkillGapDashboard() {
  const [data, setData] = useState<SkillGap | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<SkillGap>('/analysis/skill-gap')
      .then(({ data: result }) => setData(result))
      .catch(() => setError('We could not load your skill gap analysis.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <main className="skill-gap-page">
        <div className="skill-gap-loading">Loading your skill gap analysis...</div>
      </main>
    )
  }

  if (error) {
    return (
      <main className="skill-gap-page">
        <div className="error-state" role="alert">
          <strong>Unable to load analysis</strong>
          <span>{error}</span>
        </div>
      </main>
    )
  }

  if (!data?.has_analysis) {
    return (
      <main className="skill-gap-page">
        <div className="skill-gap-empty">
          <div className="empty-icon">
            <Icon name="spark" />
          </div>
          <p className="page-kicker">A clearer next step</p>
          <h1>Build your skill signal.</h1>
          <p>Run a Resume Fit analysis first. We will use its real matching and missing skills to map your learning priorities here.</p>
          <Link className="button button-small" to="/analysis">
            Create your first analysis <Icon name="arrow" />
          </Link>
        </div>
      </main>
    )
  }

  const comparison = [
    { name: 'Matching', value: data.matching_skills.length },
    { name: 'Missing', value: data.missing_skills.length },
  ]

  const distribution = [1, 2, 3, 4, 5]
    .map((level) => ({
      name: `Priority ${level}`,
      value: data.skill_priorities.filter((item) => item.priority === level).length,
    }))
    .filter((item) => item.value)

  const colors = ['#277c5b', '#4d82ae', '#f6d77a', '#e96856', '#9e86ca']

  return (
    <main className="skill-gap-page">
      <div className="skill-gap-heading">
        <div>
          <p className="page-kicker">Skill gap analysis</p>
          <h1>Where to grow next.</h1>
          <p>
            {data.job_title} at {data.company} · Compared with {data.resume_name}
          </p>
        </div>
        <Link className="button button-small" to="/analysis">
          Run new analysis <Icon name="refresh" />
        </Link>
      </div>

      <section className="skill-gap-summary">
        <div>
          <span>Overall match</span>
          <strong>{data.match_percentage}%</strong>
          <small>From your latest resume fit analysis</small>
        </div>
        <div>
          <span>Matching skills</span>
          <strong>{data.matching_skills.length}</strong>
          <small>Skills already reflected in the role</small>
        </div>
        <div>
          <span>Learning areas</span>
          <strong>{data.recommended_learning_areas.length}</strong>
          <small>Recommended from missing skills</small>
        </div>
      </section>

      <div className="skill-gap-charts">
        <article className="skill-chart">
          <h2>Skill match percentage</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[{ name: 'Match', value: data.match_percentage }]} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis type="category" dataKey="name" width={55} tickLine={false} axisLine={false} />
              <Tooltip formatter={(value) => [`${value}%`, 'Match']} />
              <Bar dataKey="value" fill="#277c5b" radius={[0, 4, 4, 0]} barSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </article>

        <article className="skill-chart">
          <h2>Matching vs missing skills</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={comparison} margin={{ top: 20, right: 15, left: -20 }}>
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#277c5b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </article>

        <article className="skill-chart">
          <h2>Skill priority distribution</h2>
          {distribution.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={distribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {distribution.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ textAlign: 'center', color: '#728087', padding: '60px 20px' }}>No priority distribution data available</p>
          )}
        </article>
      </div>

      <div className="skill-gap-lower">
        <article className="skill-chart">
          <h2>Matching skills</h2>
          {data.matching_skills.length > 0 ? (
            <ul className="priority-list">
              {data.matching_skills.slice(0, 8).map((skill) => (
                <li key={skill}>
                  <span>{skill}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: '#728087', fontSize: '12px' }}>No matching skills found yet</p>
          )}
        </article>

        <article className="skill-chart">
          <h2>Skills to develop</h2>
          {data.missing_skills.length > 0 ? (
            <ul className="priority-list">
              {data.missing_skills.slice(0, 8).map((skill) => (
                <li key={skill}>
                  <span>{skill}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: '#728087', fontSize: '12px' }}>Your skills match perfectly!</p>
          )}
        </article>

        <article className="skill-chart">
          <h2>Recommended focus areas</h2>
          {data.recommended_learning_areas.length > 0 ? (
            <ul className="priority-list">
              {data.recommended_learning_areas.map((skill) => (
                <li key={skill}>
                  <span>{skill}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: '#728087', fontSize: '12px' }}>No specific recommendations</p>
          )}
        </article>
      </div>
    </main>
  )
}
