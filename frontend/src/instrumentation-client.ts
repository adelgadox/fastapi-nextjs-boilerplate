// Sentry initialization in the browser.
//
// The file name is not decorative: @sentry/nextjs 10 loads
// `instrumentation-client.ts` and no longer reads `sentry.client.config.ts`,
// which was the name in previous versions. With the old name the file exists,
// looks correct, and nothing loads it, so no browser error ever reaches Sentry
// no matter how well the DSN is configured.
import * as Sentry from "@sentry/nextjs"

import { sentryEnvironment } from "@/lib/sentry-environment"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: sentryEnvironment(),
  tracesSampleRate: 0.2,
  // Only record the session when there was an error. Recording continuously
  // would burn through the free quota in days and almost everything recorded
  // would be healthy traffic.
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0.05,
  integrations: [Sentry.replayIntegration()],
})

// Instruments App Router navigations. Without this, a route transition opens
// no trace and the error shows up orphaned from the navigation that caused it.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart
