"use server"

import { signIn, signOut } from "@/auth"
import { AuthError } from "next-auth"
import { redirect } from "next/navigation"
import { revalidatePath } from "next/cache"
import { apiFetch, ApiError } from "@/lib/api"

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function loginAction(_: unknown, formData: FormData) {
  const rawCallback = (formData.get("callbackUrl") as string | null) ?? ""
  // Only allow same-origin relative paths — an absolute URL here would be an
  // open redirect after login.
  const callbackUrl =
    rawCallback.startsWith("/") && !rawCallback.startsWith("//") ? rawCallback : "/dashboard"

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
  const email = formData.get("email") as string

  try {
    await apiFetch("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password: formData.get("password"),
        username: formData.get("username"),
        full_name: formData.get("full_name") || undefined,
      }),
    })
  } catch (error) {
    if (error instanceof ApiError) {
      // Branch on the machine-readable code, not the human message.
      if (error.code === "EMAIL_TAKEN") return { error: "Email already registered", field: "email" }
      if (error.code === "USERNAME_TAKEN")
        return { error: "Username already taken", field: "username" }
      return { error: error.message, field: error.field }
    }
    return { error: "Registration failed" }
  }

  // redirect() throws; it must run outside the try/catch above.
  redirect(`/verify-email?email=${encodeURIComponent(email)}`)
}

export async function logoutAction() {
  // Backend revocation of the refresh token family (and the access token)
  // happens in the NextAuth signOut event (src/auth.ts), which reads the
  // refresh token from the encrypted cookie without ever exposing it here.
  // This action only ends the local session.
  await signOut({ redirectTo: "/login" })
}

export async function revalidateDashboardAction(): Promise<void> {
  revalidatePath("/dashboard", "layout")
}
