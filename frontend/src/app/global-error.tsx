"use client" // Error boundaries must be Client Components.

import { useEffect } from "react"

// Last resort: activates when the root layout itself fails, so it replaces the
// whole document and must bring its own <html>/<body> tags. It does not
// inherit the app's global styles, which is why the styles are inline and not
// Tailwind classes.
export default function GlobalError({
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
    console.error(error)
  }, [error])

  const doRetry = retry ?? unstable_retry ?? reset

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          padding: "1.5rem",
          textAlign: "center",
          fontFamily: "system-ui, sans-serif",
          color: "#1a1a1a",
        }}
      >
        <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Something went wrong</h1>
        <p style={{ maxWidth: "28rem", fontSize: "0.875rem", color: "#525252" }}>
          An unexpected error occurred. It may be temporary; please try again.
        </p>
        <button
          onClick={() => doRetry?.()}
          style={{
            marginTop: "0.5rem",
            borderRadius: "0.5rem",
            border: "none",
            background: "#18181b",
            padding: "0.625rem 1.25rem",
            fontSize: "0.875rem",
            fontWeight: 500,
            color: "#fff",
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  )
}
