import type { FeedEvent } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  bug_fix: "bg-red-100 text-red-700",
  workaround: "bg-orange-100 text-orange-700",
  configuration: "bg-blue-100 text-blue-700",
  domain_expertise: "bg-purple-100 text-purple-700",
  tooling: "bg-green-100 text-green-700",
  architecture: "bg-indigo-100 text-indigo-700",
  other: "bg-gray-100 text-gray-700",
};

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

interface FeedItemProps {
  event: FeedEvent;
}

export default function FeedItem({ event }: FeedItemProps) {
  const categoryColor =
    CATEGORY_COLORS[event.category] ?? "bg-gray-100 text-gray-700";
  const categoryLabel = event.category.replace(/_/g, " ");

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${categoryColor}`}
            >
              {categoryLabel}
            </span>
            {event.org_name && (
              <span className="text-xs text-gray-500 truncate">
                {event.org_name}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {event.title}
          </h3>
        </div>
        <span className="flex-shrink-0 text-xs text-gray-400 whitespace-nowrap">
          {relativeTime(event.created_at)}
        </span>
      </div>
    </div>
  );
}
