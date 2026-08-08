import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import Google from "next-auth/providers/google"
import type { JWT } from "next-auth/jwt"

const API_URL = process.env.API_URL ?? "http://localhost:8000"

// Margin to renew before the access token really expires: avoids using a token
// that dies halfway through a request.
const REFRESH_SKEW_MS = 60_000

// Fallback when the backend omits `expires_in` (matches the backend's
// 30-minute access token TTL). The normal path never needs it: login and
// refresh both return `expires_in` in seconds.
const DEFAULT_ACCESS_TTL_MS = 30 * 60 * 1000

// Epoch ms at which the access token expires, from the backend's `expires_in`.
// No JWT decoding needed — the backend states the TTL explicitly. (If a future
// backend drops `expires_in`, decode `exp` with an edge-safe base64: `atob`
// with a `Buffer` fallback, since `Buffer` does not exist in the edge runtime.)
function _expiresAt(expiresIn: unknown): number {
  const ttlMs = typeof expiresIn === "number" ? expiresIn * 1000 : DEFAULT_ACCESS_TTL_MS
  return Date.now() + ttlMs
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  // The NextAuth cookie lives as long as the backend refresh token (30 days):
  // while the refresh is alive, the session renews itself in the jwt callback.
  // The access token is short-lived and renewed underneath; its expiry no
  // longer ends the session.
  session: { strategy: "jwt", maxAge: 60 * 60 * 24 * 30 },
  providers: [
    Credentials({
      credentials: {
        identifier: { label: "Email or username" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const form = new URLSearchParams()
        form.append("username", credentials.identifier as string)
        form.append("password", credentials.password as string)

        const res = await fetch(`${API_URL}/v1/auth/login`, {
          method: "POST",
          body: form,
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error?.code ?? data.error?.message ?? "Invalid credentials")
        }

        const data = await res.json()
        return {
          accessToken: data.access_token,
          refreshToken: data.refresh_token ?? "",
          accessTokenExpires: _expiresAt(data.expires_in),
        }
      },
    }),
    // Uncomment to enable Google OAuth:
    // Google({
    //   clientId: process.env.GOOGLE_CLIENT_ID!,
    //   clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    // }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken
        token.refreshToken = user.refreshToken
        token.accessTokenExpires = user.accessTokenExpires
        return token
      }

      // Access token still valid (with margin): keep it as is.
      if (token.accessTokenExpires && Date.now() < token.accessTokenExpires - REFRESH_SKEW_MS) {
        return token
      }

      // Access token expired or about to: renew it with the refresh token. On
      // failure, mark the error so the middleware sends the user to /login
      // instead of leaving the session holding a dead token.
      return await _refreshAccessToken(token)
    },
    async session({ session, token }) {
      // The refresh token is NOT exposed in the session: it is long-lived and
      // lives only in the encrypted server-side cookie, never in what the
      // client sees.
      session.accessToken = token.accessToken
      session.accessTokenExpires = token.accessTokenExpires
      session.error = token.error
      return session
    },
  },
  events: {
    // On sign-out, revoke the refresh token family on the backend so a leaked
    // token does not stay alive. Done here, server-side, with the token from
    // the cookie: the refresh token never passes through the client.
    async signOut(message) {
      const token = "token" in message ? message.token : null
      const refreshToken = (token as JWT | null)?.refreshToken
      const accessToken = (token as JWT | null)?.accessToken
      if (refreshToken) {
        await fetch(`${API_URL}/v1/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        }).catch(() => {})
      }
    },
  },
  pages: {
    signIn: "/login",
  },
})

async function _refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    if (!token.refreshToken) throw new Error("no refresh token")
    const res = await fetch(`${API_URL}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token.refreshToken }),
    })
    if (!res.ok) throw new Error("refresh failed")
    const data = await res.json()
    return {
      ...token,
      accessToken: data.access_token,
      // The refresh token rotates: store the new one. If the backend did not
      // return one, keep the previous instead of leaving the session without.
      refreshToken: data.refresh_token ?? token.refreshToken,
      accessTokenExpires: _expiresAt(data.expires_in),
      error: undefined,
    }
  } catch {
    // Never throw from the jwt callback: returning the error marker lets the
    // middleware turn it into a clean /login?expired=1 redirect.
    return { ...token, error: "RefreshAccessTokenError" }
  }
}
