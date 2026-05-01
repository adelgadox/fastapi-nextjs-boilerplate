// ── User ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  avatar_url: string | null
  role: "user" | "admin" | "superadmin"
  plan: "free" | "pro"
  is_active: boolean
  is_verified: boolean
  created_at: string
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthSession {
  accessToken: string
  username: string
  role: string
}

// Add your project-specific types below
