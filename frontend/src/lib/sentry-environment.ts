/** Environment reported to Sentry.
 *
 * The precedence order matters and every rung exists for a reason:
 *
 * 1. `NEXT_PUBLIC_SENTRY_ENVIRONMENT` wins over everything: it is the explicit
 *    browser-visible override. Without it there would be no way to force the
 *    client's environment label from the dashboard.
 * 2. `SENTRY_ENVIRONMENT` is what the Vercel↔Sentry integration injects
 *    (values like `vercel-production` / `vercel-preview`). Ignoring it would
 *    split the event history into two sets of environments naming the same
 *    thing.
 * 3. `NEXT_PUBLIC_VERCEL_ENV` and 4. `VERCEL_ENV` distinguish `production`,
 *    `preview` and `development`. Both names are needed: only variables with
 *    the `NEXT_PUBLIC_` prefix reach the browser, so on the client side the
 *    unprefixed version does not exist.
 * 5. `NODE_ENV` is the last resort and only useful outside Vercel. There it is
 *    `production` even when building a preview, so if reporting ever falls
 *    through to it, errors from a branch under review land mixed in with
 *    production's.
 * 6. `"development"` is the final fallback so the value is never undefined.
 *
 * Configuration requirement: for rungs 3–4 to work in the browser, Vercel must
 * have "Automatically expose System Environment Variables" enabled, or
 * `NEXT_PUBLIC_VERCEL_ENV` defined by hand. Without that the client silently
 * falls through to rung 5.
 */
export function sentryEnvironment(): string {
  return (
    process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ??
    process.env.SENTRY_ENVIRONMENT ??
    process.env.NEXT_PUBLIC_VERCEL_ENV ??
    process.env.VERCEL_ENV ??
    process.env.NODE_ENV ??
    "development"
  )
}
