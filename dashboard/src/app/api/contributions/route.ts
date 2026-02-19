export async function GET(request: Request) {
  const apiUrl = process.env.HIVEMIND_API_URL ?? "http://localhost:8000";
  const apiKey =
    request.headers.get("X-API-Key") ??
    process.env.HIVEMIND_API_KEY ??
    "";

  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") ?? "50";
  const offset = searchParams.get("offset") ?? "0";

  const upstreamUrl = `${apiUrl}/api/v1/contributions?limit=${limit}&offset=${offset}`;

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
      },
    });

    const data = await upstreamResponse.json();
    return Response.json(data, { status: upstreamResponse.status });
  } catch {
    return Response.json(
      { error: "Failed to fetch contributions" },
      { status: 502 }
    );
  }
}
