"use client" // Error boundaries must be Client Components.

import { useEffect } from "react"

// App-wide boundary under the root layout. Catches an unhandled exception in a
// segment's render and offers to retry without a full reload.
//
// Prop naming across Next 16: 16.2 passes `unstable_retry` (re-fetch and
// re-render) alongside the legacy `reset`; 16.3 stabilizes it as `retry`.
// Accept all three so the boilerplate works on any 16.x.
export default function ErrorPage({
  error,
  retry,
  unstable_retry,
  reset,
}: {
  error: Error & { digest?: string }
  retry?: () => void
  unstable_retry?: () => void
  reset?: () => void
}) {
  useEffect(() => {
    // Sentry already captures unhandled exceptions on its own; this leaves a
    // trace in the browser console for debugging in development.
    console.error(error)
  }, [error])

  const doRetry = retry ?? unstable_retry ?? reset

  return (
    <main className="min-h-[70vh] flex flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        An unexpected error occurred while rendering this page. It may be
        temporary; please try again.
      </p>
      <button
        onClick={() => doRetry?.()}
        className="mt-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        Try again
      </button>
    </main>
  )
}
