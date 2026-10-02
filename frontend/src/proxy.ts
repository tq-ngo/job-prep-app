import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Edge guard for authenticated routes.
 *
 * NOTE ON THE FILENAME: in Next 16 the `middleware` file convention is
 * deprecated and renamed to `proxy`, exporting a function named `proxy`.
 * See node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md
 *
 * This is an OPTIMISTIC check only — it reads the session cookie and nothing
 * else. Per Next's own guidance, proxy runs on every request including
 * prefetches, so it must not hit the database or call the API. The
 * authoritative check lives server-side: /api/v1/jobs/ now requires auth, and
 * the jobs server component forwards cookies on its fetch. Both layers are
 * needed — previously there was no guard at all AND the API accepted
 * anonymous callers, so /jobs shipped job data to logged-out visitors.
 */

const PROTECTED_PREFIXES = ['/jobs', '/news']
const AUTH_PAGES = ['/login', '/register']

function hasValidSession(request: NextRequest): boolean {
  const token = request.cookies.get('access_token')?.value
  if (!token) return false
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false
    // Payload is the second base64url part
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = typeof atob !== 'undefined'
      ? atob(base64)
      : Buffer.from(base64, 'base64').toString('utf-8')
    const payload = JSON.parse(json)
    if (payload.exp && typeof payload.exp === 'number') {
      const nowSec = Math.floor(Date.now() / 1000)
      if (payload.exp <= nowSec) {
        return false // Expired token
      }
    }
    return true
  } catch {
    return false
  }
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl

  // HttpOnly cookie: readable here on the server, verified for basic expiration.
  const hasSession = hasValidSession(request)

  const isProtected = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  )
  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p))

  if (isProtected && !hasSession) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    // Preserve where they were heading so login can send them back.
    url.search = `?next=${encodeURIComponent(pathname + search)}`
    return NextResponse.redirect(url)
  }

  // Already signed in with a valid session? Don't show the login form.
  if (isAuthPage && hasSession) {
    const url = request.nextUrl.clone()
    url.pathname = '/jobs'
    url.search = ''
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  // Without a matcher this runs on every request including _next/static and
  // public assets, which would make auth logic block CSS/JS from loading.
  matcher: ['/jobs/:path*', '/news/:path*', '/login', '/register'],
}
