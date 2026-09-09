import { useAuthContext } from './auth-context'

export function useAuth() {
  return useAuthContext()
}
