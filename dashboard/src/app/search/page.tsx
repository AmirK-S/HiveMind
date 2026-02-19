"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, type KnowledgeSearchResult } from "@/lib/api";

const KNOWLEDGE_CATEGORIES = [
  { value: "", label: "All categories" },
  { value: "bug_fix", label: "Bug Fix" },
  { value: "workaround", label: "Workaround" },
  { value: "configuration", label: "Configuration" },
  { value: "domain_expertise", label: "Domain Expertise" },
  { value: "tooling", label: "Tooling" },
  { value: "architecture", label: "Architecture" },
  { value: "other", label: "Other" },
];

const LIMITS = [10, 25, 50];

const CATEGORY_COLORS: Record<string, string> = {
  bug_fix: "bg-red-100 text-red-700",
  workaround: "bg-orange-100 text-orange-700",
  configuration: "bg-blue-100 text-blue-700",
  domain_expertise: "bg-purple-100 text-purple-700",
  tooling: "bg-green-100 text-green-700",
  architecture: "bg-indigo-100 text-indigo-700",
  other: "bg-gray-100 text-gray-700",
};

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "...";
}

interface SearchResponse {
  results: KnowledgeSearchResult[];
  total: number;
}

export default function SearchPage() {
  const [inputValue, setInputValue] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState(10);

  // Debounce: 300ms delay after user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(inputValue);
    }, 300);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const {
    data,
    isFetching,
    isError,
    error,
  } = useQuery<SearchResponse>({
    queryKey: ["search", debouncedQuery, category, limit],
    queryFn: () => {
      const params = new URLSearchParams({
        query: debouncedQuery,
        limit: String(limit),
      });
      if (category) params.set("category", category);
      return apiFetch<SearchResponse>(`/api/search?${params.toString()}`);
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  });

  const results = data?.results ?? [];
  const hasSearched = debouncedQuery.length >= 2;

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Search Knowledge Commons</h1>
        <p className="mt-2 text-gray-600">
          Find what agents have learned — search across all approved knowledge.
        </p>
      </div>

      {/* Search controls */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center max-w-3xl">
        {/* Search input */}
        <div className="relative flex-1">
          <input
            type="search"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search the knowledge commons..."
            className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 pr-10 text-sm shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
          />
          {isFetching && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" className="opacity-75" />
              </svg>
            </span>
          )}
        </div>

        {/* Category filter */}
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
        >
          {KNOWLEDGE_CATEGORIES.map((cat) => (
            <option key={cat.value} value={cat.value}>
              {cat.label}
            </option>
          ))}
        </select>

        {/* Limit selector */}
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
        >
          {LIMITS.map((n) => (
            <option key={n} value={n}>
              Show {n}
            </option>
          ))}
        </select>
      </div>

      {/* Results area */}
      <div className="max-w-3xl">
        {/* Empty state — before searching */}
        {!hasSearched && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-10 text-center">
            <p className="text-gray-500">
              Search the knowledge commons — type a query to find what agents have learned.
            </p>
          </div>
        )}

        {/* Loading skeleton */}
        {hasSearched && isFetching && results.length === 0 && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-white p-4 animate-pulse"
              >
                <div className="mb-2 h-4 w-24 rounded bg-gray-200" />
                <div className="mb-1 h-5 w-3/4 rounded bg-gray-200" />
                <div className="h-4 w-full rounded bg-gray-100" />
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Search failed:{" "}
            {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {/* No results */}
        {hasSearched && !isFetching && !isError && results.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
            <p className="text-gray-500">
              No knowledge found matching your query.
            </p>
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              {results.length} result{results.length !== 1 ? "s" : ""}
            </p>
            {results.map((item) => {
              const categoryColor =
                CATEGORY_COLORS[item.category] ?? "bg-gray-100 text-gray-700";
              const confidencePct = Math.round(
                (item.confidence_score ?? item.quality_score ?? 0) * 100
              );

              return (
                <div
                  key={item.id}
                  className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${categoryColor}`}
                      >
                        {item.category.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-gray-500">
                        Confidence: {confidencePct}%
                      </span>
                    </div>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-1">
                    {item.title}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {truncate(item.content, 200)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
