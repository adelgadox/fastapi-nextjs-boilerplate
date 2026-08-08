import { auth } from "@/auth"
import { NextResponse } from "next/server"

export default auth((req) => {
  const session = req.auth
  // The access token renews itself with the refresh token (jwt callback). The
  // session is treated as closed only when the refresh failed — it really
  // ended — to bounce to /login instead of leaving a panel with a dead token.
  const isExpired = !!session && session.error === "RefreshAccessTokenError"
  const isLoggedIn = !!session && !isExpired
  const { pathname } = req.nextUrl

  const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register")
  const isDashboard = pathname.startsWith("/dashboard")

  if (isDashboard && !isLoggedIn) {
    // Clone nextUrl and change only pathname/search so nothing about the
    // origin is rebuilt by hand; building with string templates would mangle
    // existing query strings.
    const url = req.nextUrl.clone()
    url.pathname = "/login"
    url.search = ""
    if (isExpired) {
      // Surface a "your session expired" notice instead of a silent bounce.
      url.searchParams.set("expired", "1")
    } else {
      // Preserve path + query string so post-login lands back where the user
      // was headed (e.g. /dashboard/settings?tab=billing).
      url.searchParams.set("callbackUrl", pathname + req.nextUrl.search)
    }
    return NextResponse.redirect(url)
  }

  if (isAuthPage && isLoggedIn) {
    const url = req.nextUrl.clone()
    url.pathname = "/dashboard"
    url.search = ""
    return NextResponse.redirect(url)
  }

  const res = NextResponse.next()
  // Authenticated shells must never be restored from the browser's
  // back/forward cache — otherwise a user whose session expired could still
  // see the old dashboard by pressing "back". no-store disables bfcache for
  // these routes, forcing a fresh request that re-runs this auth check.
  if (isDashboard) {
    res.headers.set("Cache-Control", "no-store, must-revalidate")
  }
  return res
})

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/register"],
}
