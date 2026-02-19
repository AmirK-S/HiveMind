export const runtime = "nodejs";

export async function GET(request: Request) {
  const apiUrl = process.env.HIVEMIND_API_URL ?? "http://localhost:8000";
  const apiKey =
    request.headers.get("X-API-Key") ??
    process.env.HIVEMIND_API_KEY ??
    "";

  const upstreamUrl = `${apiUrl}/api/v1/stream/feed`;

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstreamUrl, {
      headers: {
        "X-API-Key": apiKey,
        Accept: "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  } catch {
    // Upstream not available — return error event stream
    const errorStream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            'event: error\ndata: {"message":"upstream unavailable"}\n\n'
          )
        );
        controller.close();
      },
    });
    return new Response(errorStream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  if (!upstreamResponse.ok || !upstreamResponse.body) {
    const fallback = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            `event: error\ndata: {"status":${upstreamResponse.status}}\n\n`
          )
        );
        controller.close();
      },
    });
    return new Response(fallback, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // Pipe upstream SSE body directly to the client
  const stream = upstreamResponse.body;

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
