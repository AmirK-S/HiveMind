// operation_id: knowledge_search_proxy
// Proxies to GET /api/v1/knowledge/search on the HiveMind API

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  const query = searchParams.get("query") ?? "";
  const limit = searchParams.get("limit") ?? "10";
  const category = searchParams.get("category") ?? "";

  const apiUrl = process.env.HIVEMIND_API_URL ?? "http://localhost:8000";
  const apiKey =
    request.headers.get("X-API-Key") ??
    process.env.HIVEMIND_API_KEY ??
    "";

  const params = new URLSearchParams({ query, limit });
  if (category) {
    params.set("category", category);
  }

  const upstreamUrl = `${apiUrl}/api/v1/knowledge/search?${params.toString()}`;

  try {
    const response = await fetch(upstreamUrl, {
      headers: {
        "X-API-Key": apiKey,
        Accept: "application/json",
      },
    });

    const data = await response.json();

    return Response.json(data, { status: response.status });
  } catch {
    return Response.json(
      { error: "Search service unavailable" },
      { status: 503 }
    );
  }
}
