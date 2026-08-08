import Link from "next/link"
import { apiFetch, ApiError } from "@/lib/api"

// Two modes:
// - ?email=… (right after registering): "check your inbox" notice.
// - ?token=… (link clicked in the email): verifies server-side against the
//   backend and shows the outcome.
export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; email?: string }>
}) {
  const { token, email } = await searchParams

  let heading = "Verify your email"
  let message: string
  let verified = false

  if (token) {
    try {
      const res = await apiFetch<{ message: string }>(
        `/v1/auth/verify-email?token=${encodeURIComponent(token)}`
      )
      verified = true
      heading = "Email verified"
      message =
        res.message === "already_verified"
          ? "This email was already verified. You can sign in."
          : "Your email has been verified. You can sign in now."
    } catch (error) {
      heading = "Verification failed"
      message =
        error instanceof ApiError
          ? error.message
          : "We could not verify your email. The link may have expired."
    }
  } else if (email) {
    message = `We sent a verification link to ${email}. Check your inbox to activate your account.`
  } else {
    message = "Open the verification link we sent to your email address."
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md space-y-4 text-center">
        <h1 className="text-2xl font-semibold">{heading}</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{message}</p>
        {verified && (
          <Link
            href="/login"
            className="inline-block rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Go to sign in
          </Link>
        )}
      </div>
    </main>
  )
}
