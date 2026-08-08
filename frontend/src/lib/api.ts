// Server-side fetches bypass Cloudflare and call the backend directly (avoids
// Bot Fight Mode blocking the frontend host). Browser fetches go through
// NEXT_PUBLIC_API_URL (Cloudflare proxied).
const API_URL =
  typeof window === "undefined"
    ? (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")

type FetchOptions = RequestInit & {
  token?: string
  next?: { revalidate?: number; tags?: string[] }
}

// Error thrown on any non-2xx response. `message` is always a human-readable
// string (backward compatible with callers that only read `.message`), while
// `code` exposes the backend's machine-readable error code (e.g. `EMAIL_TAKEN`)
// so callers can branch on it, and `field` points at the offending input when
// the backend names one.
export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly field?: string

  constructor(message: string, opts: { status: number; code?: string; field?: string }) {
    super(message)
    this.name = "ApiError"
    this.status = opts.status
    this.code = opts.code
    this.field = opts.field
  }
}

// Parses the three error body shapes the backend can produce:
//   { error: { code, message, field } }  — the structured envelope (api_error)
//   { detail: { code, message, field } } — legacy envelope variant
//   { detail: "plain string" }           — FastAPI default (e.g. validation)
function parseErrorBody(body: Record<string, unknown>): {
  message: string
  code?: string
  field?: string
} {
  let message = "Request failed"
  let code: string | undefined
  let field: string | undefined

  const error = body.error as Record<string, unknown> | undefined
  const detail = body.detail

  if (error && typeof error.message === "string") {
    message = error.message
    code = typeof error.code === "string" ? error.code : undefined
    field = typeof error.field === "string" ? error.field : undefined
  } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>
    message = typeof d.message === "string" ? d.message : message
    code = typeof d.code === "string" ? d.code : undefined
    field = typeof d.field === "string" ? d.field : undefined
  } else if (typeof detail === "string") {
    message = detail
  }

  return { message, code, field }
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, ...rest } = options
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...rest.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const { message, code, field } = parseErrorBody(body)
    throw new ApiError(message, { status: res.status, code, field })
  }

  return res.json()
}
