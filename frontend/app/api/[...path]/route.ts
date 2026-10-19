import { NextRequest, NextResponse } from "next/server";

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
    return NextResponse.json(
      { detail: "The public demo runs in your browser. Server API access is disabled." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }
  const { path } = await params;
  if (
    !["public", "auth", "admin", "health"].includes(path[0]) ||
    path.some((x) => !/^[\w-]+$/.test(x))
  ) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const length = Number(request.headers.get("content-length") || 0);
  if (length > 20000)
    return NextResponse.json({ detail: "Payload too large" }, { status: 413 });
  let body: string | undefined;
  if (!["GET", "HEAD"].includes(request.method)) {
    const reader = request.body?.getReader();
    const decoder = new TextDecoder();
    const chunks: string[] = [];
    let total = 0;
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > 20000) {
          await reader.cancel();
          return NextResponse.json(
            { detail: "Payload too large" },
            { status: 413 },
          );
        }
        chunks.push(decoder.decode(value, { stream: true }));
      }
    }
    body = chunks.join("") + decoder.decode();
  }
  const headers = new Headers();
  for (const key of [
    "content-type",
    "cookie",
    "origin",
    "x-csrf-token",
    "idempotency-key",
    "x-correlation-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  // The API applies per-client rate limits to the address this proxy asserts.
  // A caller can put anything in X-Forwarded-For, so the value is only evidence
  // when a sanitising ingress sits in front of this process and overwrites it.
  // Without one, Next.js is the edge: forward nothing, let the API fall back to
  // the socket peer, and leave per-address limiting off rather than accept a
  // client-chosen identity. TRUST_UPSTREAM_FORWARDED_FOR is the operator
  // asserting that such an ingress exists.
  if (process.env.TRUST_UPSTREAM_FORWARDED_FOR === "true") {
    const forwarded = request.headers.get("x-forwarded-for");
    const clientAddress = (forwarded?.split(",")[0] ?? request.headers.get("x-real-ip") ?? "").trim();
    if (clientAddress) headers.set("x-forwarded-for", clientAddress);
  }
  try {
    const upstream = await fetch(
      `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(90000),
      },
    );
    const outgoing = new Headers({
      "Content-Type":
        upstream.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store",
    });
    for (const cookie of upstream.headers.getSetCookie())
      outgoing.append("Set-Cookie", cookie);
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) outgoing.set("Retry-After", retryAfter);
    // Pass the correlation identifier back, so a reported problem can be found
    // in the API logs without guessing.
    const correlation = upstream.headers.get("x-correlation-id");
    if (correlation) outgoing.set("X-Correlation-ID", correlation);
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: outgoing,
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "The automation API is unavailable. Retry with the same submission key.",
      },
      { status: 503 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
