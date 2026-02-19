"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import ReviewCard, { type ContributionDetail } from "@/components/contributions/ReviewCard";

interface ContributionsResponse {
  contributions?: ContributionDetail[];
  items?: ContributionDetail[];
  total?: number;
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
      <div className="flex gap-2 mb-3">
        <div className="h-5 bg-gray-200 rounded w-16" />
        <div className="h-5 bg-gray-200 rounded w-12" />
      </div>
      <div className="h-3 bg-gray-200 rounded mb-1" />
      <div className="h-3 bg-gray-200 rounded mb-1" />
      <div className="h-3 bg-gray-200 rounded w-2/3 mb-3" />
      <div className="flex gap-2">
        <div className="h-8 bg-gray-200 rounded flex-1" />
        <div className="h-8 bg-gray-200 rounded flex-1" />
      </div>
    </div>
  );
}

export default function ContributionsPage() {
  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<ContributionDetail[]>({
    queryKey: ["contributions"],
    queryFn: async () => {
      const res = await apiFetch<ContributionsResponse | ContributionDetail[]>(
        "/api/contributions?limit=50&offset=0"
      );
      // Handle both array response and object with contributions/items key
      if (Array.isArray(res)) return res;
      if (res.contributions) return res.contributions;
      if (res.items) return res.items;
      return [];
    },
    refetchInterval: 15_000,
  });

  const contributions = data ?? [];
  const count = contributions.length;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Pending Contributions</h1>
        {!isLoading && (
          <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-full text-sm font-semibold bg-indigo-100 text-indigo-700">
            {count}
          </span>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load contributions: {String(error)}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && count === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="text-5xl mb-4">&#10003;</div>
          <h2 className="text-lg font-semibold text-gray-700 mb-1">
            No pending contributions
          </h2>
          <p className="text-gray-500 text-sm">All caught up! New contributions will appear here automatically.</p>
        </div>
      )}

      {/* Contributions list */}
      {!isLoading && !isError && count > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {contributions.map((contribution) => (
            <ReviewCard key={contribution.id} contribution={contribution} />
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 mt-6 text-center">
        Auto-refreshes every 15 seconds
      </p>
    </div>
  );
}
