import { useEffect, useState, type ReactNode } from 'react'
import { api, AUTH_TOKEN_KEY } from './api'
import { AuthContext, type Credentials, type Registration } from './auth-context'
import type { User } from './auth-types'

export type { User }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => Boolean(sessionStorage.getItem(AUTH_TOKEN_KEY)))

  useEffect(() => {
    const handleUnauthorized = () => setUser(null)
    window.addEventListener('careerpilot:unauthorized', handleUnauthorized)
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (token) {
      api.get<User>('/auth/me').then(({ data }) => setUser(data)).catch(() => setUser(null)).finally(() => setLoading(false))
    }
    return () => window.removeEventListener('careerpilot:unauthorized', handleUnauthorized)
  }, [])

  async function authenticate(path: '/auth/login' | '/auth/register', data: Credentials | Registration) {
    const response = await api.post<{ access_token: string; user: User }>(path, data)
    sessionStorage.setItem(AUTH_TOKEN_KEY, response.data.access_token)
    setUser(response.data.user)
  }

  async function login(credentials: Credentials) { await authenticate('/auth/login', credentials) }
  async function register(data: Registration) { await authenticate('/auth/register', data) }
  function logout() { sessionStorage.removeItem(AUTH_TOKEN_KEY); setUser(null) }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}