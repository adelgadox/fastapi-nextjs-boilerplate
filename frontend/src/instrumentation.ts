// Server and edge instrumentation.
//
// Since Next 15 this is the file Next runs when each runtime boots; without it
// the server-side Sentry configuration exists on disk but never executes.
// Note: this project uses the `src/` layout, so the file lives in `src/`
// (a root-level instrumentation.ts would not be picked up).
import * as Sentry from "@sentry/nextjs"

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config")
    // Server calls to the backend go direct (not through Cloudflare), so they
    // add the origin secret themselves to survive CLOUDFLARE_ONLY.
    const { installBackendOriginAuth } = await import("./lib/backend-origin-auth")
    installBackendOriginAuth()
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config")
  }
}

// Errors thrown while rendering on the server. They never reach the browser
// SDK — nobody sees them client-side — nor an API handler: this hook is the
// only path by which they get to Sentry.
export const onRequestError = Sentry.captureRequestError
