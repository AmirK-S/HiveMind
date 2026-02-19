// Typed response interfaces

export interface KnowledgeSearchResult {
  id: string;
  title: string;
  content: string;
  category: string;
  quality_score: number;
  confidence_score: number;
  org_name?: string;
  created_at: string;
  tags?: string[];
}

export interface FeedEvent {
  id: string;
  type: "public" | "private";
  title: string;
  category: string;
  org_name?: string;
  org_id?: string;
  created_at: string;
  quality_score?: number;
}

export interface StatsResponse {
  total_items: number;
  total_orgs: number;
  items_last_24h: number;
  top_categories: Array<{ category: string; count: number }>;
  network_health_score?: number;
}

export interface ContributionItem {
  id: string;
  title: string;
  content: string;
  category: string;
  org_id: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  quality_score?: number;
}

// Typed fetch wrapper for Next.js route handlers (relative URLs like /api/...)
export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const apiKey =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_HIVEMIND_API_KEY
      : undefined;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
    ...(options?.headers ?? {}),
  };

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}
