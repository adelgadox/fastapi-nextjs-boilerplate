import type { NextConfig } from "next"
import { withSentryConfig } from "@sentry/nextjs"

// Some pages embed images served directly by the backend (e.g. QR codes or
// user avatars proxied through the API), so its origin has to be in img-src or
// the browser blocks the image without anything visible on the page.
// Computed at build time from NEXT_PUBLIC_API_URL; the try/catch keeps a build
// without the variable from crashing on `new URL("")`.
const apiOrigin = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_URL ?? "").origin
  } catch {
    return ""
  }
})()

const imgSrc = ["'self'", "data:", "blob:", ...(apiOrigin ? [apiOrigin] : [])].join(" ")

// Browser-side apiFetch calls hit the backend origin directly, so connect-src
// must allow it too (plus Sentry ingestion for error reports).
const connectSrc = [
  "'self'",
  "https://*.sentry.io",
  "https://*.ingest.sentry.io",
  ...(apiOrigin ? [apiOrigin] : []),
].join(" ")

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-XSS-Protection", value: "1; mode=block" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  // Nothing in the boilerplate needs camera/microphone/geolocation. Relax a
  // directive here only when a feature actually requires it.
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // 'unsafe-inline'/'unsafe-eval' are required by Next.js hydration and
      // dev tooling. Tighten with nonces per project if needed.
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      `img-src ${imgSrc}`,
      "font-src 'self'",
      `connect-src ${connectSrc}`,
      "frame-ancestors 'none'",
    ].join("; "),
  },
]

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }]
  },
  experimental: {
    // Default Server Action body limit is 1MB — too small for file uploads
    // going through server actions (e.g. avatar photos). Keep in sync with the
    // backend's own upload size cap.
    serverActions: { bodySizeLimit: "5mb" },
  },
  images: {
    // Cache optimized images for 30 days at the edge — reduces re-optimization under load.
    minimumCacheTTL: 60 * 60 * 24 * 30,
    // Restrict to common breakpoints only — fewer cache key combinations = smaller attack surface.
    deviceSizes: [640, 828, 1080, 1280, 1920],
    imageSizes: [16, 32, 64, 128, 256],
    // Single format — halves the number of cache variants.
    formats: ["image/webp"],
  },
}

// Sentry org and project come from the environment, never from code: a rename
// in Sentry changes the slug, and hardcoding it here forces a commit for what
// is account configuration.
//
// The guard exists because the opposite already happened once: with a stale
// slug the build stayed green and source maps silently stopped uploading for a
// month. Having the token but no destination is an unambiguous mistake, so the
// build fails loudly instead of staying quiet. Without a token there is
// nothing to upload and the guard does not get in the way.
if (process.env.SENTRY_AUTH_TOKEN && !(process.env.SENTRY_ORG && process.env.SENTRY_PROJECT)) {
  throw new Error(
    "SENTRY_AUTH_TOKEN is set but SENTRY_ORG or SENTRY_PROJECT is missing: " +
      "the build would upload source maps to nowhere, silently."
  )
}

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Browser events leave through a route on this domain instead of going
  // straight to sentry.io. Ad-blocker lists include the ingestion domain, so
  // without this the errors of anyone browsing with a blocker are lost — and
  // not at random: exactly that segment disappears, leaving a skewed picture
  // that looks complete.
  tunnelRoute: "/monitoring",
  silent: !process.env.CI,
  // Applies to both webpack and turbopack builds.
  widenClientFileUpload: true,
  // Root-level `disableLogger` and `automaticVercelMonitors` are deprecated
  // since @sentry/nextjs 10: they now live under `webpack` because they have no
  // effect on Turbopack builds, and grouping them makes that explicit.
  webpack: {
    treeshake: { removeDebugLogging: true },
    automaticVercelMonitors: true,
  },
})
