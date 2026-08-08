import { RegisterForm } from "./register-form"

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-semibold">Create an account</h1>
        <RegisterForm />
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Already have an account?{" "}
          <a href="/login" className="font-medium underline">
            Sign in
          </a>
        </p>
      </div>
    </main>
  )
}
