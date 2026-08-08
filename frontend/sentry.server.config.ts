import * as Sentry from "@sentry/nextjs"

import { sentryEnvironment } from "@/lib/sentry-environment"

Sentry.init({
  // The server DSN may differ from the browser one; when it is not defined the
  // public one is used, which is the normal single-Sentry-project case.
  dsn: process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: sentryEnvironment(),
  tracesSampleRate: 0.2,
})
