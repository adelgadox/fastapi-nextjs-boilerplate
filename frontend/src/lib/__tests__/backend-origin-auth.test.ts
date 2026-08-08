import { describe, expect, it, vi } from "vitest"
import { makeOriginAuthFetch } from "../backend-origin-auth"

/* The interceptor adds X-Origin-Auth only to requests to the backend origin.
 * It is what lets server-to-server calls through when the backend enables
 * CLOUDFLARE_ONLY, without exposing the secret to anyone else or touching
 * other destinations (CDNs, third-party APIs, etc.). */

const BASE = "https://api.internal.example"
const SECRET = "test-s3cr3t"

function spyFetch() {
  return vi.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(null, { status: 200 }),
  )
}

describe("makeOriginAuthFetch", () => {
  it("adds the secret header on requests to the backend origin", async () => {
    const original = spyFetch()
    const wrapped = makeOriginAuthFetch(original, BASE, SECRET)

    await wrapped(`${BASE}/v1/users`, { headers: { Authorization: "Bearer x" } })

    const init = original.mock.calls[0][1] as RequestInit
    const headers = new Headers(init.headers)
    expect(headers.get("X-Origin-Auth")).toBe(SECRET)
    // Does not clobber headers that were already there.
    expect(headers.get("Authorization")).toBe("Bearer x")
  })

  it("leaves requests to other hosts untouched", async () => {
    const original = spyFetch()
    const wrapped = makeOriginAuthFetch(original, BASE, SECRET)

    await wrapped("https://example.org/api/x")

    const init = (original.mock.calls[0][1] ?? {}) as RequestInit
    const headers = new Headers(init.headers)
    expect(headers.get("X-Origin-Auth")).toBeNull()
  })

  it("works when no init is passed", async () => {
    const original = spyFetch()
    const wrapped = makeOriginAuthFetch(original, BASE, SECRET)

    await wrapped(`${BASE}/v1/health`)

    const init = original.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get("X-Origin-Auth")).toBe(SECRET)
  })
})
