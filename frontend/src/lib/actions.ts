"use server"

import { signIn, signOut, auth } from "@/auth"
import { AuthError } from "next-auth"
import { redirect } from "next/navigation"
import { revalidatePath } from "next/cache"
import { apiFetch } from "@/lib/api"

const API_URL = process.env.API_URL ?? "http://localhost:8000"

function extractError(detail: unknown, fallback = "Something went wrong"): string {
  if (!detail) return fallback
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) return detail[0]?.msg ?? fallback
  return fallback
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function loginAction(_: unknown, formData: FormData) {
  const callbackUrl = (formData.get("callbackUrl") as string | null) || "/dashboard"
  try {
    await signIn("credentials", {
      identifier: formData.get("identifier") as string,
      password: formData.get("password") as string,
      redirectTo: callbackUrl,
    })
  } catch (error) {
    if (error instanceof AuthError) {
      const msg = (error.cause?.err as Error | undefined)?.message ?? ""
      if (msg === "EMAIL_NOT_VERIFIED") return { error: "email_not_verified" }
      if (msg === "ACCOUNT_DISABLED") return { error: "account_disabled" }
      return { error: "Invalid email or password" }
    }
    throw error
  }
}

export async function registerAction(_: unknown, formData: FormData) {
  const body = {
    email: formData.get("email"),
    password: formData.get("password"),
    username: formData.get("username"),
    full_name: formData.get("full_name") || undefined,
  }

  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    return { error: extractError(data.detail, "Registration failed") }
  }

  redirect(`/verify-email?email=${encodeURIComponent(body.email as string)}`)
}

export async function logoutAction() {
  const session = await auth()
  if (session?.accessToken) {
    await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.accessToken}` },
    }).catch(() => {})
  }
  await signOut({ redirectTo: "/login" })
}

export async function revalidateDashboardAction(): Promise<void> {
  revalidatePath("/dashboard", "layout")
}
