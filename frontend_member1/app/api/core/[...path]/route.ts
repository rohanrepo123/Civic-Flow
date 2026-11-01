type RouteContext = { params: Promise<{ path: string[] }> }

const forwardedHeaders = ["content-type", "cache-control", "location"]

async function forward(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params
  if (path[0] !== "api" || path[1] !== "v1" || path.some((part) => part === "." || part === ".." || part.includes("/") || part.includes("\\"))) {
    return Response.json({ detail: "Unknown Core API route." }, { status: 404 })
  }

  let upstreamUrl: URL
  try {
    upstreamUrl = new URL(process.env.CORE_API_URL || "http://127.0.0.1:8000")
    if (upstreamUrl.protocol !== "http:" && upstreamUrl.protocol !== "https:") throw new Error("Unsupported API protocol")
  } catch {
    return Response.json({ detail: "Core API is not configured." }, { status: 503 })
  }

  upstreamUrl.pathname = `/${path.map(encodeURIComponent).join("/")}`
  upstreamUrl.search = new URL(request.url).search

  const headers = new Headers(request.headers)
  for (const header of ["host", "connection", "content-length", "accept-encoding"]) headers.delete(header)
  const method = request.method.toUpperCase()

  try {
    const upstream = await fetch(upstreamUrl, {
      method,
      headers,
      body: method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    })
    const responseHeaders = new Headers()
    for (const header of forwardedHeaders) {
      const value = upstream.headers.get(header)
      if (value) responseHeaders.set(header, value)
    }
    for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append("set-cookie", cookie)
    const bodyless = method === "HEAD" || [204, 205, 304].includes(upstream.status)
    return new Response(bodyless ? null : await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    })
  } catch {
    return Response.json({ detail: "CivicFlow could not reach the Core API. Check that local services are running." }, { status: 503 })
  }
}

export const GET = forward
export const HEAD = forward
export const POST = forward
export const PUT = forward
export const PATCH = forward
export const DELETE = forward
