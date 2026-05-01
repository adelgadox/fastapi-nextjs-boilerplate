import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import Google from "next-auth/providers/google"

const API_URL = process.env.API_URL ?? "http://localhost:8000"

export const { handlers, signIn, signOut, auth } = NextAuth({
  session: { strategy: "jwt" },
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

        const res = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          body: form,
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail ?? "Invalid credentials")
        }

        const data = await res.json()
        return { accessToken: data.access_token }
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
        // @ts-expect-error — custom field
        token.accessToken = user.accessToken
      }
      return token
    },
    async session({ session, token }) {
      // @ts-expect-error — custom field
      session.accessToken = token.accessToken
      return session
    },
  },
  pages: {
    signIn: "/login",
  },
})
