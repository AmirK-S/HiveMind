"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface ContributionDetail {
  id: string;
  content: string;
  category: string;
  source_agent_id?: string;
  org_id?: string;
  submitted_at?: string;
  created_at?: string;
  content_hash?: string;
  status?: string;
}

interface ReviewCardProps {
  contribution: ContributionDetail;
}

const CATEGORY_COLORS: Record<string, string> = {
  general: "bg-gray-100 text-gray-700",
  code: "bg-blue-100 text-blue-700",
  research: "bg-purple-100 text-purple-700",
  documentation: "bg-green-100 text-green-700",
  bug: "bg-red-100 text-red-700",
  feature: "bg-yellow-100 text-yellow-700",
};

function relativeTime(dateStr?: string): string {
  if (!dateStr) return "Unknown time";
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function truncateHash(hash?: string): string {
  if (!hash) return "N/A";
  return hash.length > 16 ? `${hash.slice(0, 8)}...${hash.slice(-8)}` : hash;
}

export default function ReviewCard({ contribution }: ReviewCardProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [copied, setCopied] = useState(false);

  const title = contribution.content.slice(0, 80) + (contribution.content.length > 80 ? "..." : "");
  const preview = contribution.content.slice(0, 200);
  const categoryColor =
    CATEGORY_COLORS[contribution.category?.toLowerCase()] ??
    "bg-gray-100 text-gray-700";
  const timestamp = contribution.submitted_at ?? contribution.created_at;

  const approveMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/contributions/${contribution.id}/approve`, {
        method: "POST",
      }),
    onMutate: async () => {
      // Optimistic update: remove card from list
      await queryClient.cancelQueries({ queryKey: ["contributions"] });
      const previous = queryClient.getQueryData<ContributionDetail[]>(["contributions"]);
      queryClient.setQueryData<ContributionDetail[]>(["contributions"], (old) =>
        old ? old.filter((c) => c.id !== contribution.id) : []
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(["contributions"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["contributions"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/contributions/${contribution.id}/reject`, {
        method: "POST",
      }),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["contributions"] });
      const previous = queryClient.getQueryData<ContributionDetail[]>(["contributions"]);
      queryClient.setQueryData<ContributionDetail[]>(["contributions"], (old) =>
        old ? old.filter((c) => c.id !== contribution.id) : []
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["contributions"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["contributions"] });
      setShowRejectConfirm(false);
    },
  });

  const isMutating = approveMutation.isPending || rejectMutation.isPending;

  function copyHash() {
    if (contribution.content_hash) {
      navigator.clipboard.writeText(contribution.content_hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm truncate">{title}</h3>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span
              className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${categoryColor}`}
            >
              {contribution.category}
            </span>
            <span className="text-xs text-gray-400">{relativeTime(timestamp)}</span>
          </div>
        </div>
      </div>

      {/* Content preview */}
      <div className="text-sm text-gray-600">
        {expanded ? (
          <p className="whitespace-pre-wrap break-words">{contribution.content}</p>
        ) : (
          <p className="line-clamp-3">{preview}</p>
        )}
        {contribution.content.length > 200 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-indigo-600 hover:text-indigo-800 text-xs mt-1 font-medium"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
        <div>
          <span className="font-medium text-gray-700">Agent: </span>
          <span className="font-mono">{contribution.source_agent_id ?? "N/A"}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="font-medium text-gray-700">Hash: </span>
          <span className="font-mono">{truncateHash(contribution.content_hash)}</span>
          {contribution.content_hash && (
            <button
              onClick={copyHash}
              className="text-indigo-500 hover:text-indigo-700 ml-1"
              title="Copy full hash"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => approveMutation.mutate()}
          disabled={isMutating}
          className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-1"
        >
          {approveMutation.isPending ? (
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            "Approve"
          )}
        </button>

        {!showRejectConfirm ? (
          <button
            onClick={() => setShowRejectConfirm(true)}
            disabled={isMutating}
            className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white rounded-md text-sm font-medium transition-colors"
          >
            Reject
          </button>
        ) : (
          <div className="flex-1 flex items-center gap-1">
            <span className="text-xs text-red-600 font-medium">Sure?</span>
            <button
              onClick={() => rejectMutation.mutate()}
              disabled={isMutating}
              className="px-2 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white rounded text-xs font-medium flex items-center gap-1"
            >
              {rejectMutation.isPending ? (
                <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                "Yes, Reject"
              )}
            </button>
            <button
              onClick={() => setShowRejectConfirm(false)}
              className="px-2 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-xs font-medium"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Error states */}
      {(approveMutation.isError || rejectMutation.isError) && (
        <p className="text-xs text-red-600">Action failed. Please try again.</p>
      )}
    </div>
  );
}
