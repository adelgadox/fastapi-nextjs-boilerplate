"use client"

import { useActionState } from "react"
import { loginAction } from "@/lib/actions"

// Machine codes returned by loginAction, mapped to user-facing copy here so
// the server action stays presentation-free.
const ERROR_MESSAGES: Record<string, string> = {
  email_not_verified: "Your email is not verified yet. Check your inbox.",
  account_disabled: "This account is disabled.",
}

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "dark:border-zinc-700 dark:bg-zinc-900"

export function LoginForm({ callbackUrl }: { callbackUrl: string }) {
  const [state, formAction, pending] = useActionState(loginAction, undefined)
  const error = state?.error ? (ERROR_MESSAGES[state.error] ?? state.error) : null

  return (
    <form action={formAction} className="space-y-4">
      <input type="hidden" name="callbackUrl" value={callbackUrl} />
      <label className="block space-y-1">
        <span className="text-sm font-medium">Email or username</span>
        <input name="identifier" required autoComplete="username" className={inputClass} />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Password</span>
        <input
          name="password"
          type="password"
          required
          autoComplete="current-password"
          className={inputClass}
        />
      </label>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  )
}
