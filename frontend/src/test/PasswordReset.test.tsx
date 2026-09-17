import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AuthProvider } from '../lib/auth'
import { api } from '../lib/api'

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Forgot and Reset Password flows', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders "Forgot password?" link on the login page and navigates to /forgot-password', async () => {
    const client = userEvent.setup()
    renderApp('/login')

    const forgotLink = screen.getByRole('link', { name: /forgot password\?/i })
    expect(forgotLink).toBeInTheDocument()

    await client.click(forgotLink)
    expect(await screen.findByRole('heading', { name: /forgot password/i })).toBeInTheDocument()
    expect(screen.getByText(/enter your registered email address/i)).toBeInTheDocument()
  })

  it('submits forgot-password form and shows generic success message', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({
      data: {
        message: 'If an account exists for this email address, a password reset link has been generated.',
        dev_reset_url: 'http://localhost:5173/reset-password?token=sample-test-token',
      },
    } as never)

    const client = userEvent.setup()
    renderApp('/forgot-password')

    const emailInput = screen.getByLabelText(/email/i)
    await client.type(emailInput, 'pilot@example.com')
    await client.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(
      await screen.findByText(/if an account exists for this email address/i),
    ).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/auth/forgot-password', {
      email: 'pilot@example.com',
    })
    expect(screen.getByRole('link', { name: /open reset password link/i })).toBeInTheDocument()
  })

  it('shows missing token warning on /reset-password if token param is absent', async () => {
    renderApp('/reset-password')

    expect(await screen.findByRole('alert')).toHaveTextContent(/no reset token found/i)
    expect(screen.getByRole('link', { name: /request new link/i })).toBeInTheDocument()
  })

  it('successfully resets password with valid token and shows Return to Login', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({
      data: {
        message: 'Your password has been reset successfully. You can now log in with your new password.',
      },
    } as never)

    const client = userEvent.setup()
    renderApp('/reset-password?token=valid-token-123')

    expect(await screen.findByRole('heading', { name: /set new password/i })).toBeInTheDocument()

    await client.type(screen.getByLabelText(/^new password$/i), 'super-secret-password')
    await client.type(screen.getByLabelText(/^confirm new password$/i), 'super-secret-password')
    await client.click(screen.getByRole('button', { name: /reset password/i }))

    expect(
      await screen.findByText(/your password has been reset successfully/i),
    ).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/auth/reset-password', {
      token: 'valid-token-123',
      new_password: 'super-secret-password',
      confirm_password: 'super-secret-password',
    })
    expect(screen.getByRole('link', { name: /return to login/i })).toBeInTheDocument()
  })

  it('validates client-side password mismatch on reset password', async () => {
    const postSpy = vi.spyOn(api, 'post')
    const client = userEvent.setup()
    renderApp('/reset-password?token=valid-token-123')

    await client.type(screen.getByLabelText(/^new password$/i), 'password-one-123')
    await client.type(screen.getByLabelText(/^confirm new password$/i), 'password-two-456')
    await client.click(screen.getByRole('button', { name: /reset password/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/passwords do not match/i)
    expect(postSpy).not.toHaveBeenCalled()
  })

  it('displays API error if reset token is invalid or expired', async () => {
    vi.spyOn(api, 'post').mockRejectedValue({
      response: {
        data: {
          detail: 'Invalid or expired password reset link. Please request a new one.',
        },
      },
    })

    const client = userEvent.setup()
    renderApp('/reset-password?token=expired-token')

    await client.type(screen.getByLabelText(/^new password$/i), 'new-password-123')
    await client.type(screen.getByLabelText(/^confirm new password$/i), 'new-password-123')
    await client.click(screen.getByRole('button', { name: /reset password/i }))

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(/invalid or expired password reset link/i)
  })
})
