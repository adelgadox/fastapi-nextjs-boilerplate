"use client"

import { useActionState } from "react"
import { registerAction } from "@/lib/actions"

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "dark:border-zinc-700 dark:bg-zinc-900"

function FieldError({ state, field }: { state: { error?: string; field?: string } | undefined; field: string }) {
  if (!state?.error || state.field !== field) return null
  return <p className="text-sm text-red-600 dark:text-red-400">{state.error}</p>
}

export function RegisterForm() {
  const [state, formAction, pending] = useActionState(registerAction, undefined)

  return (
    <form action={formAction} className="space-y-4">
      <label className="block space-y-1">
        <span className="text-sm font-medium">Email</span>
        <input name="email" type="email" required autoComplete="email" className={inputClass} />
        <FieldError state={state} field="email" />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Username</span>
        <input name="username" required autoComplete="username" className={inputClass} />
        <FieldError state={state} field="username" />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Full name (optional)</span>
        <input name="full_name" autoComplete="name" className={inputClass} />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Password</span>
        <input
          name="password"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          className={inputClass}
        />
      </label>
      {/* General (non-field) error */}
      {state?.error && !state.field && (
        <p className="text-sm text-red-600 dark:text-red-400">{state.error}</p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "Creating account…" : "Create account"}
      </button>
    </form>
  )
}
