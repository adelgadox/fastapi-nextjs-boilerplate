// Module augmentation for the custom token fields we thread from the FastAPI
// backend through NextAuth's JWT session. Without this, `authorize()`'s return
// value, `token.*`, and `session.*` are untyped.
import type { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    accessToken?: string
    accessTokenExpires?: number
    // "RefreshAccessTokenError" when renewing the access token failed — the
    // middleware treats the session as ended and redirects to /login.
    error?: string
    user: DefaultSession["user"]
  }

  interface User {
    accessToken?: string
    refreshToken?: string
    accessTokenExpires?: number
  }
}

// The JWT interface lives in @auth/core/jwt; next-auth/jwt only re-exports it,
// so augmentation must target the core module to merge.
declare module "@auth/core/jwt" {
  interface JWT {
    accessToken?: string
    // Lives only here (encrypted server-side cookie); never copied to Session.
    refreshToken?: string
    accessTokenExpires?: number
    error?: string
  }
}
