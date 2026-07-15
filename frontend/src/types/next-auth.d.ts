// Module augmentation for the custom `accessToken` field we thread from the
// FastAPI backend through NextAuth's JWT session. Without this, `authorize()`'s
// return value, `token.accessToken`, and `session.accessToken` are untyped.
import type { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    accessToken?: string
    user: DefaultSession["user"]
  }

  interface User {
    accessToken?: string
  }
}

// The JWT interface lives in @auth/core/jwt; next-auth/jwt only re-exports it,
// so augmentation must target the core module to merge.
declare module "@auth/core/jwt" {
  interface JWT {
    accessToken?: string
  }
}
