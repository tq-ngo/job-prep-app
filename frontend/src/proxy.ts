import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Edge guard for authenticated routes.
 *
 * NOTE ON THE FILENAME: in Next 16 the `middleware` file convention is
 * deprecated and renamed to `proxy`, exporting a function named `proxy`.
 * Proxy runs on the Node.js runtime, so Web Crypto and runtime env vars are
 * available here.
 *
 * The access token's HS256 signature and claims are verified here, not just
 * base64-decoded: previously any well-formed unsigned token got past the
 * edge. The API remains the authoritative check; this layer exists so that
 * protected pages never render for a caller without a genuine session.
 *
 * Proxy must not call the database or API (it runs on every request,
 * including prefetches), so an expired access token is handled by
 * redirecting to /api/v1/auth/resume, which can see the path-scoped refresh
 * cookie, rotates it, and sends the browser back here.
 */

const PROTECTED_PREFIXES = ['/jobs', '/news']
const AUTH_PAGES = ['/login', '/register']

// Must match backend/app/core/security.py.
const ISSUER = 'job-prep-app'
const AUDIENCE = 'job-prep-app:api'

// Set when we send the browser to /resume. If it comes back still without a
// verifiable token (e.g. JWT_SECRET out of sync with the backend), go to
// /login instead of looping proxy -> resume -> proxy forever.
const RESUME_GUARD_COOKIE = 'auth_resume_attempt'
const RESUME_GUARD_SECONDS = 15

// Non-HttpOnly, path=/, same lifetime as the refresh token: a cheap hint
// that a refresh token probably exists, so logged-out visitors skip the
// /resume round trip.
const SESSION_HINT_COOKIE = 'csrf_token'

const encoder = new TextEncoder()
let keyPromise: Promise<CryptoKey> | null = null
let warnedNoSecret = false

function getKey(secret: string): Promise<CryptoKey> {
  keyPromise ??= crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify'],
  )
  return keyPromise
}

function b64urlToBytes(segment: string): Uint8Array<ArrayBuffer> {
  const b64 = segment.replace(/-/g, '+').replace(/_/g, '/')
  const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4)
  const bin = atob(padded)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

function decodeJson(segment: string): Record<string, unknown> {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(segment)))
}

async function hasValidSession(request: NextRequest): Promise<boolean> {
  const token = request.cookies.get('access_token')?.value
  if (!token) return false

  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false
    const [h, p, sig] = parts

    const header = decodeJson(h)
    if (header.alg !== 'HS256') return false // pin alg: rejects "none" etc.

    const secret = process.env.JWT_SECRET
    if (secret) {
      const ok = await crypto.subtle.verify(
        'HMAC',
        await getKey(secret),
        b64urlToBytes(sig),
        encoder.encode(`${h}.${p}`),
      )
      if (!ok) return false
    } else if (!warnedNoSecret) {
      // Fail open to the API's own check rather than locking everyone out
      // (or looping): the backend still rejects forged tokens on every call.
      warnedNoSecret = true
      console.error('proxy: JWT_SECRET is unset; access tokens are NOT signature-verified at the edge')
    }

    const payload = decodeJson(p)
    const now = Math.floor(Date.now() / 1000)
    if (payload.typ !== 'access') return false
    if (payload.iss !== ISSUER || payload.aud !== AUDIENCE) return false
    if (typeof payload.exp !== 'number' || payload.exp <= now) return false
    if (typeof payload.nbf === 'number' && payload.nbf > now + 30) return false
    return true
  } catch {
    return false
  }
}

function redirectToLogin(request: NextRequest, next: string) {
  const url = request.nextUrl.clone()
  url.pathname = '/login'
  url.search = `?next=${encodeURIComponent(next)}`
  const res = NextResponse.redirect(url)
  res.cookies.delete(RESUME_GUARD_COOKIE)
  return res
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hasSession = await hasValidSession(request)

  const isProtected = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  )
  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p))

  if (isProtected && !hasSession) {
    const next = pathname + search
    const mayHaveRefresh = request.cookies.has(SESSION_HINT_COOKIE)
    const alreadyTried = request.cookies.has(RESUME_GUARD_COOKIE)
    if (!mayHaveRefresh || alreadyTried) {
      return redirectToLogin(request, next)
    }

    const url = request.nextUrl.clone()
    url.pathname = '/api/v1/auth/resume'
    url.search = `?next=${encodeURIComponent(next)}`
    const res = NextResponse.redirect(url)
    res.cookies.set(RESUME_GUARD_COOKIE, '1', {
      maxAge: RESUME_GUARD_SECONDS,
      httpOnly: true,
      sameSite: 'lax',
      path: '/',
    })
    return res
  }

  // Already signed in with a valid session? Don't show the login form.
  if (isAuthPage && hasSession) {
    const url = request.nextUrl.clone()
    url.pathname = '/jobs'
    url.search = ''
    return NextResponse.redirect(url)
  }

  const res = NextResponse.next()
  if (hasSession && request.cookies.has(RESUME_GUARD_COOKIE)) {
    res.cookies.delete(RESUME_GUARD_COOKIE)
  }
  return res
}

export const config = {
  // Without a matcher this runs on every request including _next/static and
  // public assets, which would make auth logic block CSS/JS from loading.
  matcher: ['/jobs/:path*', '/news/:path*', '/login', '/register'],
}
