import { createContext, useContext } from 'react'
import type { User } from './auth-types'

export type Credentials = { email: string; password: string }
export type Registration = Credentials & { name: string; confirm_password: string }
export type AuthContextValue = { user: User | null; loading: boolean; login: (credentials: Credentials) => Promise<void>; register: (data: Registration) => Promise<void>; logout: () => void }

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuthContext() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
