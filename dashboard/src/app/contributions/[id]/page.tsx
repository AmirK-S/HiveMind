"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useState } from "react";

interface KnowledgeItemDetail {
  id: string;
  title?: string;
  content: string;
  category: string;
  source_agent_id?: string;
  org_id?: string;
  contributed_at?: string;
  created_at?: string;
  content_hash?: string;
  quality_score?: number;
  retrieval_count?: number;
  helpful_count?: number;
  not_helpful_count?: number;
  is_public?: boolean;
  valid_at?: string;
  expired_at?: string;
  status?: string;
  tags?: string[];
}

const CATEGORY_COLORS: Record<string, string> = {
  general: "bg-gray-100 text-gray-700",
  code: "bg-blue-100 text-blue-700",
  research: "bg-purple-100 text-purple-700",
  documentation: "bg-green-100 text-green-700",
  bug: "bg-red-100 text-red-700",
  feature: "bg-yellow-100 text-yellow-700",
};

function QualityBar({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  const color =
    score < 0.3
      ? "bg-red-500"
      : score < 0.6
      ? "bg-yellow-500"
      : "bg-green-500";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full ${color} transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm font-medium text-gray-700 w-10 text-right">
        {percentage}%
      </span>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-gray-900 break-all">{value}</span>
    </div>
  );
}

export default function ContributionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;

  const [copied, setCopied] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);

  const { data: item, isLoading, isError } = useQuery<KnowledgeItemDetail>({
    queryKey: ["knowledge", id],
    queryFn: () => apiFetch<KnowledgeItemDetail>(`/api/knowledge/${id}`),
    retry: 1,
  });

  const approveMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/contributions/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contributions"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge", id] });
      router.push("/contributions");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/contributions/${id}/reject`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contributions"] });
      router.push("/contributions");
    },
  });

  function copyHash() {
    if (item?.content_hash) {
      navigator.clipboard.writeText(item.content_hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const isPending = item?.status === "pending" || !item?.quality_score;
  const isMutating = approveMutation.isPending || rejectMutation.isPending;

  const displayTitle =
    item?.title ?? (item?.content ? item.content.slice(0, 80) : "Untitled");
  const categoryColor =
    CATEGORY_COLORS[(item?.category ?? "").toLowerCase()] ??
    "bg-gray-100 text-gray-700";
  const helpfulTotal =
    (item?.helpful_count ?? 0) + (item?.not_helpful_count ?? 0);
  const helpfulRatio =
    helpfulTotal > 0
      ? Math.round(((item?.helpful_count ?? 0) / helpfulTotal) * 100)
      : null;

  const contributedDate = item?.contributed_at ?? item?.created_at;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Back link */}
      <button
        onClick={() => router.back()}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-6 flex items-center gap-1"
      >
        &larr; Back
      </button>

      {isLoading && (
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-2/3" />
          <div className="h-4 bg-gray-200 rounded w-1/4" />
          <div className="h-40 bg-gray-200 rounded" />
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load knowledge item. It may not exist or you may not have access.
        </div>
      )}

      {item && (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left: Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-3 mb-4 flex-wrap">
              <h1 className="text-2xl font-bold text-gray-900 flex-1 min-w-0">
                {displayTitle}
              </h1>
              <span
                className={`inline-block px-2.5 py-0.5 rounded text-sm font-medium ${categoryColor}`}
              >
                {item.category}
              </span>
              <span
                className={`inline-block px-2.5 py-0.5 rounded text-sm font-medium ${
                  item.is_public
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {item.is_public ? "Public" : "Private"}
              </span>
            </div>

            {/* Full content */}
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
              <pre className="whitespace-pre-wrap break-words text-sm text-gray-800 font-sans">
                {item.content}
              </pre>
            </div>

            {/* Tags */}
            {item.tags && item.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {item.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* Approve/reject for pending items */}
            {isPending && (
              <div className="mt-6 flex items-center gap-3">
                <button
                  onClick={() => approveMutation.mutate()}
                  disabled={isMutating}
                  className="px-6 py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {approveMutation.isPending ? (
                    <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : null}
                  Approve
                </button>

                {!showRejectConfirm ? (
                  <button
                    onClick={() => setShowRejectConfirm(true)}
                    disabled={isMutating}
                    className="px-6 py-2.5 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white rounded-md text-sm font-medium transition-colors"
                  >
                    Reject
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-red-600 font-medium">Confirm reject?</span>
                    <button
                      onClick={() => rejectMutation.mutate()}
                      disabled={isMutating}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white rounded text-sm font-medium flex items-center gap-1"
                    >
                      {rejectMutation.isPending ? (
                        <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : null}
                      Yes, Reject
                    </button>
                    <button
                      onClick={() => setShowRejectConfirm(false)}
                      className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-sm font-medium"
                    >
                      Cancel
                    </button>
                  </div>
                )}

                {(approveMutation.isError || rejectMutation.isError) && (
                  <p className="text-sm text-red-600">Action failed. Please try again.</p>
                )}
              </div>
            )}
          </div>

          {/* Right: Provenance sidebar */}
          <div className="lg:w-80 shrink-0 space-y-4">
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 space-y-4">
              <h2 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
                Provenance
              </h2>

              <MetaRow
                label="Contributed by agent"
                value={
                  <span className="font-mono text-xs">
                    {item.source_agent_id ?? "N/A"}
                  </span>
                }
              />

              <MetaRow
                label="Organization"
                value={item.org_id ?? "N/A"}
              />

              <MetaRow
                label="Contributed At"
                value={
                  contributedDate
                    ? new Date(contributedDate).toLocaleString()
                    : "N/A"
                }
              />

              <div className="flex flex-col gap-0.5">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Content Hash (SHA-256)
                </span>
                <div className="flex items-center gap-1">
                  <span className="font-mono text-xs text-gray-800 break-all flex-1">
                    {item.content_hash ?? "N/A"}
                  </span>
                  {item.content_hash && (
                    <button
                      onClick={copyHash}
                      className="shrink-0 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      {copied ? "Copied!" : "Copy"}
                    </button>
                  )}
                </div>
              </div>

              {item.quality_score !== undefined && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Quality Score
                  </span>
                  <QualityBar score={item.quality_score} />
                </div>
              )}

              <MetaRow
                label="Retrieval Count"
                value={item.retrieval_count ?? 0}
              />

              {helpfulRatio !== null && (
                <MetaRow
                  label="Helpful / Not Helpful"
                  value={
                    <span>
                      {item.helpful_count ?? 0} / {item.not_helpful_count ?? 0}{" "}
                      <span className="text-gray-500">({helpfulRatio}% helpful)</span>
                    </span>
                  }
                />
              )}

              {item.valid_at && (
                <MetaRow
                  label="Valid From"
                  value={new Date(item.valid_at).toLocaleDateString()}
                />
              )}

              {item.expired_at && (
                <MetaRow
                  label="Expired At"
                  value={new Date(item.expired_at).toLocaleDateString()}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
