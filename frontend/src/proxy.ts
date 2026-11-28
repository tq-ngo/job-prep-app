import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Edge guard for authenticated routes.
 *
 * NOTE ON THE FILENAME: in Next 16 the `middleware` file convention is
 * deprecated and renamed to `proxy`, exporting a function named `proxy`.
 * Proxy runs on the Node.js runtime, so Web Crypto and runtime env vars are
 * available here.
 */

const PROTECTED_PREFIXES = ['/jobs', '/news']
const AUTH_PAGES = ['/login', '/register']

// Must match backend/app/core/security.py.
const ISSUER = 'job-prep-app'
const AUDIENCE = 'job-prep-app:api'

// Refresh access tokens 5s before hard expiry so a token verified here cannot
// expire milliseconds later before (app)/layout.tsx calls /api/v1/auth/me.
const EXPIRY_BUFFER_SECONDS = 5

const RESUME_GUARD_COOKIE = 'auth_resume_attempt'
const RESUME_GUARD_SECONDS = 15
const SESSION_HINT_COOKIE = 'csrf_token'

export const SESSION_INVALID_REASON = 'session_invalid'
export const PATHNAME_HEADER = 'x-app-pathname'

const encoder = new TextEncoder()
const keyCache = new Map<string, Promise<CryptoKey>>()
let warnedNoSecret = false

function signingSecret(): string | undefined {
  return process.env.JWT_SECRET || process.env.SECRET_KEY || undefined
}

function cookieDomain(): string | undefined {
  const domain = process.env.COOKIE_DOMAIN?.trim()
  return domain || undefined
}

function isSecureRequest(request: NextRequest): boolean {
  if (process.env.COOKIE_SECURE === 'true') return true
  const forwardedProto = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim().toLowerCase()
  if (forwardedProto === 'https') return true
  return request.nextUrl.protocol === 'https:'
}

function setNoStore(res: NextResponse): NextResponse {
  res.headers.set('Cache-Control', 'private, no-store')
  res.headers.set('Vary', 'Cookie')
  return res
}

function cleanNextPath(pathname: string, search: string): string {
  if (!search) return pathname
  const params = new URLSearchParams(search)
  params.delete('_rsc')
  const cleaned = params.toString()
  return cleaned ? `${pathname}?${cleaned}` : pathname
}

/**
 * Background router prefetches (<Link> in the viewport or on hover).
 * Returning 204 declines the prefetch without rotating tokens or caching
 * a /login redirect as the link's target.
 */
function isPrefetch(request: NextRequest): boolean {
  const h = request.headers
  return (
    h.has('next-router-prefetch') ||
    h.has('next-router-segment-prefetch') ||
    h.get('purpose') === 'prefetch' ||
    (h.get('sec-purpose') ?? '').includes('prefetch')
  )
}

function getKey(secret: string): Promise<CryptoKey> {
  let cached = keyCache.get(secret)
  if (!cached) {
    if (keyCache.size >= 4) {
      keyCache.clear()
    }
    cached = crypto.subtle.importKey(
      'raw',
      encoder.encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify'],
    )
    keyCache.set(secret, cached)
  }
  return cached
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
    if (header.alg !== 'HS256') return false

    const secret = signingSecret()
    if (secret) {
      const ok = await crypto.subtle.verify(
        'HMAC',
        await getKey(secret),
        b64urlToBytes(sig),
        encoder.encode(`${h}.${p}`),
      )
      if (!ok) return false
    } else if (process.env.NODE_ENV === 'development') {
      if (!warnedNoSecret) {
        warnedNoSecret = true
        console.warn('proxy: JWT_SECRET is unset; skipping edge signature check (dev only)')
      }
    } else {
      if (!warnedNoSecret) {
        warnedNoSecret = true
        console.error('proxy: JWT_SECRET is unset; rejecting all sessions at the edge until it is configured')
      }
      return false
    }

    const payload = decodeJson(p)
    const now = Math.floor(Date.now() / 1000)
    if (payload.typ !== 'access') return false
    if (payload.iss !== ISSUER || payload.aud !== AUDIENCE) return false
    if (typeof payload.sub !== 'string' || !payload.sub) return false
    if (typeof payload.jti !== 'string' || !payload.jti) return false
    if (typeof payload.iat !== 'number') return false
    if (typeof payload.exp !== 'number' || payload.exp <= now + EXPIRY_BUFFER_SECONDS) return false
    if (typeof payload.nbf === 'number' && payload.nbf > now + 30) return false
    return true
  } catch {
    return false
  }
}

function deleteCookieWithScope(res: NextResponse, name: string) {
  const domain = cookieDomain()
  if (domain) {
    res.cookies.delete({ name, path: '/', domain })
  } else {
    res.cookies.delete(name)
  }
}

function redirectToLogin(request: NextRequest, next: string) {
  const url = request.nextUrl.clone()
  url.pathname = '/login'
  url.search = `?next=${encodeURIComponent(next)}`
  const res = setNoStore(NextResponse.redirect(url))
  deleteCookieWithScope(res, RESUME_GUARD_COOKIE)
  return res
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hasSession = await hasValidSession(request)

  const isProtected = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  )
  const isAuthPage = AUTH_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`))

  if (isProtected && !hasSession) {
    if (isPrefetch(request)) {
      // Decline all unauthenticated protected-route prefetches (whether or not
      // csrf_token is present) so hovering/viewing <Link href="/jobs"> never
      // rotates tokens or caches a 307 -> /login redirect.
      return setNoStore(new NextResponse(null, { status: 204 }))
    }

    const next = cleanNextPath(pathname, search)
    const mayHaveRefresh = request.cookies.has(SESSION_HINT_COOKIE)
    const alreadyTried = request.cookies.has(RESUME_GUARD_COOKIE)
    if (!mayHaveRefresh || alreadyTried) {
      return redirectToLogin(request, next)
    }

    const url = request.nextUrl.clone()
    url.pathname = '/api/v1/auth/resume'
    url.search = `?next=${encodeURIComponent(next)}`
    const res = setNoStore(NextResponse.redirect(url))
    const domain = cookieDomain()
    res.cookies.set(RESUME_GUARD_COOKIE, '1', {
      maxAge: RESUME_GUARD_SECONDS,
      httpOnly: true,
      secure: isSecureRequest(request),
      sameSite: 'lax',
      path: '/',
      ...(domain ? { domain } : {}),
    })
    return res
  }

  if (isAuthPage && hasSession) {
    if (request.nextUrl.searchParams.get('reason') === SESSION_INVALID_REASON) {
      const sanitizedHeaders = new Headers(request.headers)
      sanitizedHeaders.delete(PATHNAME_HEADER)
      const res = setNoStore(NextResponse.next({ request: { headers: sanitizedHeaders } }))
      deleteCookieWithScope(res, 'access_token')
      deleteCookieWithScope(res, RESUME_GUARD_COOKIE)
      return res
    }
    const url = request.nextUrl.clone()
    url.pathname = '/jobs'
    url.search = ''
    return setNoStore(NextResponse.redirect(url))
  }

  const forwardedHeaders = new Headers(request.headers)
  if (isProtected) {
    forwardedHeaders.set(PATHNAME_HEADER, cleanNextPath(pathname, search))
  } else {
    // Strip any client-supplied x-app-pathname on non-protected routes.
    forwardedHeaders.delete(PATHNAME_HEADER)
  }

  const res = NextResponse.next({ request: { headers: forwardedHeaders } })
  if (hasSession && request.cookies.has(RESUME_GUARD_COOKIE)) {
    deleteCookieWithScope(res, RESUME_GUARD_COOKIE)
  }
  return res
}

export const config = {
  matcher: ['/jobs/:path*', '/news/:path*', '/login/:path*', '/register/:path*'],
}
