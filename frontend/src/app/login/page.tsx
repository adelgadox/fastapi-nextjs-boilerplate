import { LoginForm } from "./login-form"

// Server component: reads the query string (Next 16: searchParams is a
// Promise) and hands plain props to the client form.
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ expired?: string; callbackUrl?: string }>
}) {
  const params = await searchParams
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-semibold">Sign in</h1>
        {params.expired === "1" && (
          <p className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            Your session expired. Please sign in again.
          </p>
        )}
        <LoginForm callbackUrl={params.callbackUrl ?? ""} />
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          No account?{" "}
          <a href="/register" className="font-medium underline">
            Register
          </a>
        </p>
      </div>
    </main>
  )
}
