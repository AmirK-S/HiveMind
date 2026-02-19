export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const apiUrl = process.env.HIVEMIND_API_URL ?? "http://localhost:8000";
  const apiKey =
    request.headers.get("X-API-Key") ??
    process.env.HIVEMIND_API_KEY ??
    "";

  const upstreamUrl = `${apiUrl}/api/v1/contributions/${id}/approve`;

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
      },
    });

    const data = await upstreamResponse.json();
    return Response.json(data, { status: upstreamResponse.status });
  } catch {
    return Response.json(
      { error: "Failed to approve contribution" },
      { status: 502 }
    );
  }
}
