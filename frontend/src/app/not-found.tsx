import Link from "next/link"

// App-wide 404. Shown when a route does not exist or a segment calls
// notFound().
export default function NotFound() {
  return (
    <main className="min-h-[70vh] flex flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-5xl font-bold text-zinc-900 dark:text-zinc-100">404</p>
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        The link may be broken or the page may have moved.
      </p>
      <Link
        href="/"
        className="mt-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        Back to home
      </Link>
    </main>
  )
}
