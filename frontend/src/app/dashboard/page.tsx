import { auth } from "@/auth"
import { logoutAction } from "@/lib/actions"
import { apiFetch, ApiError } from "@/lib/api"
import type { User } from "@/types"

// Minimal authenticated page: the middleware already guards /dashboard, so a
// session is expected here. Fetches the current user from the backend to show
// the full auth loop (cookie → access token → API) working.
export default async function DashboardPage() {
  const session = await auth()

  let user: User | null = null
  let loadError: string | null = null
  if (session?.accessToken) {
    try {
      user = await apiFetch<User>("/v1/auth/me", { token: session.accessToken })
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : "Could not load your profile"
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl space-y-6 px-6 py-16">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <form action={logoutAction}>
          <button
            type="submit"
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium dark:border-zinc-700"
          >
            Sign out
          </button>
        </form>
      </div>

      {user ? (
        <div className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
          <p>
            Signed in as <span className="font-medium">{user.username}</span> ({user.email})
          </p>
          <p className="mt-1 text-zinc-600 dark:text-zinc-400">
            Role: {user.role} · Plan: {user.plan}
          </p>
        </div>
      ) : (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {loadError ?? "No profile data available."}
        </p>
      )}
    </main>
  )
}
