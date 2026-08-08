/* Adds the `X-Origin-Auth` header to every request from the Next.js server to
 * the backend, in a single place.
 *
 * When the backend enables `CLOUDFLARE_ONLY`, it rejects any request that does
 * not carry that secret. Browser traffic goes through Cloudflare, which injects
 * the header with a Transform Rule; but server-to-server calls from the
 * frontend host (route handlers, server actions, `apiFetch` on the server) go
 * **directly** to the backend, without passing through Cloudflare, so they have
 * to add the secret themselves. Without this, enabling `CLOUDFLARE_ONLY` would
 * take down every server-rendered page that talks to the API.
 *
 * It is done as a single interceptor on the global `fetch`, not by editing each
 * call site, on purpose: a security control you have to remember to add in
 * every spot gets forgotten in call site number 55. The interceptor only
 * touches requests whose URL points at the backend origin (`API_URL`); any
 * other fetch (third-party APIs, CDNs) is left intact. Without
 * `CLOUDFLARE_SHARED_SECRET` configured it is a no-op: deploying it before the
 * secret exists changes nothing.
 */

type FetchFn = typeof fetch

/** Wraps a `fetch` to inject `X-Origin-Auth` on requests to the `base` origin.
 * Exported separately from the install step so it can be tested without
 * touching the global `fetch`. */
export function makeOriginAuthFetch(original: FetchFn, base: string, secret: string): FetchFn {
  return (input, init) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.href : input.url
    if (!url.startsWith(base)) {
      return original(input, init)
    }
    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined),
    )
    headers.set("X-Origin-Auth", secret)
    return original(input, { ...init, headers })
  }
}

let installed = false

/** Installs the interceptor on `globalThis.fetch`. Idempotent. No-op if the
 * secret or the backend base URL is missing. */
export function installBackendOriginAuth(): void {
  if (installed) return
  const secret = process.env.CLOUDFLARE_SHARED_SECRET
  const base = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL
  if (!secret || !base) return
  installed = true
  globalThis.fetch = makeOriginAuthFetch(globalThis.fetch, base, secret)
}
