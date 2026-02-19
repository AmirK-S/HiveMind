"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import StatsCard from "@/components/charts/StatsCard";
import GrowthChart, { type GrowthDataPoint } from "@/components/charts/GrowthChart";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

// ---------------------------------------------------------------------------
// Types matching FastAPI CommonsStatsResponse and OrgStatsResponse
// ---------------------------------------------------------------------------

interface CategoryCount {
  category: string;
  count: number;
}

interface CommonsStats {
  total_items: number;
  total_pending: number;
  growth_rate_24h: number;
  growth_rate_7d: number;
  retrieval_volume_24h: number;
  domains_covered: number;
  categories: CategoryCount[];
}

interface TopItem {
  id: string;
  title: string;
  retrieval_count: number;
}

interface OrgStats {
  contributions_total: number;
  contributions_pending: number;
  contributions_approved_24h: number;
  retrievals_by_others: number;
  helpful_count: number;
  not_helpful_count: number;
  top_items: TopItem[];
}

// ---------------------------------------------------------------------------
// Skeleton loading state
// ---------------------------------------------------------------------------

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="h-4 bg-gray-200 rounded w-2/3 mb-3" />
          <div className="h-8 bg-gray-200 rounded w-1/2" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generate simple growth data from stats (synthetic time-series from totals)
// ---------------------------------------------------------------------------

function buildGrowthData(growth7d: number, growth24h: number): GrowthDataPoint[] {
  const now = new Date();
  const days: GrowthDataPoint[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    // Estimate: distribute 7d growth across days, spike on last day
    const isToday = i === 0;
    const isYesterday = i === 1;
    const base = Math.round((growth7d - growth24h) / 6);
    const count = isToday ? growth24h : isYesterday ? Math.round(base * 0.8) : base;
    days.push({ date: label, count: Math.max(0, count) });
  }
  return days;
}

// ---------------------------------------------------------------------------
// Main analytics page
// ---------------------------------------------------------------------------

export default function AnalyticsPage() {
  const {
    data: commons,
    isLoading: commonsLoading,
    isError: commonsError,
  } = useQuery<CommonsStats>({
    queryKey: ["stats", "commons"],
    queryFn: () => apiFetch<CommonsStats>("/api/stats/commons"),
    refetchInterval: 30_000,
  });

  const {
    data: org,
    isLoading: orgLoading,
    isError: orgError,
  } = useQuery<OrgStats>({
    queryKey: ["stats", "org"],
    queryFn: () => apiFetch<OrgStats>("/api/stats/org"),
    refetchInterval: 30_000,
  });

  const growthData: GrowthDataPoint[] =
    commons
      ? buildGrowthData(commons.growth_rate_7d, commons.growth_rate_24h)
      : [];

  const totalFeedback =
    (org?.helpful_count ?? 0) + (org?.not_helpful_count ?? 0);
  const helpfulPercent =
    totalFeedback > 0
      ? Math.round(((org?.helpful_count ?? 0) / totalFeedback) * 100)
      : 0;

  const isInHighDemand =
    org &&
    org.retrievals_by_others > org.contributions_total;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-10">
      {/* ----------------------------------------------------------------- */}
      {/* Section 1: Commons Health */}
      {/* ----------------------------------------------------------------- */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Public Commons Health
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Aggregate metrics across the entire knowledge network
            </p>
          </div>
          <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">
            Refreshes every 30s
          </span>
        </div>

        {commonsLoading && <StatsSkeleton />}

        {commonsError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load commons stats. Retrying...
          </div>
        )}

        {commons && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <StatsCard
                title="Total Knowledge Items"
                value={commons.total_items}
                subtitle="Approved items in the commons"
                trend="up"
              />
              <StatsCard
                title="Growth (24h)"
                value={commons.growth_rate_24h}
                subtitle="New items in the last 24 hours"
                trend={commons.growth_rate_24h > 0 ? "up" : "neutral"}
              />
              <StatsCard
                title="Growth (7d)"
                value={commons.growth_rate_7d}
                subtitle="New items in the last 7 days"
                trend={commons.growth_rate_7d > 0 ? "up" : "neutral"}
              />
              <StatsCard
                title="Retrieval Volume (24h)"
                value={commons.retrieval_volume_24h}
                subtitle="Times knowledge was retrieved"
                trend={commons.retrieval_volume_24h > 0 ? "up" : "neutral"}
              />
              <StatsCard
                title="Domains Covered"
                value={commons.domains_covered}
                subtitle="Distinct knowledge categories"
              />
              <StatsCard
                title="Pending Contributions"
                value={commons.total_pending}
                subtitle="Awaiting review"
                trend={commons.total_pending > 10 ? "down" : "neutral"}
              />
            </div>

            {/* Growth chart */}
            <div className="mt-6">
              <GrowthChart data={growthData} title="Knowledge Growth (7 days)" />
            </div>

            {/* Category breakdown */}
            {commons.categories.length > 0 && (
              <div className="mt-6 bg-white rounded-lg border border-gray-200 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">
                  Items by Category
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={commons.categories}
                    layout="vertical"
                    margin={{ top: 0, right: 20, left: 20, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 12, fill: "#6b7280" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      dataKey="category"
                      type="category"
                      tick={{ fontSize: 12, fill: "#6b7280" }}
                      tickLine={false}
                      axisLine={false}
                      width={100}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "8px",
                        border: "1px solid #e5e7eb",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="count" name="Items" fill="#6366f1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </section>

      {/* ----------------------------------------------------------------- */}
      {/* Section 2: Org Reciprocity Ledger */}
      {/* ----------------------------------------------------------------- */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Your Organization
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Contribution metrics and reciprocity data for your org
            </p>
          </div>
        </div>

        {orgLoading && <StatsSkeleton />}

        {orgError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load org stats. Retrying...
          </div>
        )}

        {org && (
          <>
            {/* Gamification message */}
            {isInHighDemand && (
              <div className="mb-4 flex items-center gap-2 bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3">
                <span className="text-lg">&#9733;</span>
                <p className="text-sm font-medium text-indigo-800">
                  Your knowledge is in high demand! Your contributions have been retrieved{" "}
                  <strong>{org.retrievals_by_others}</strong> times — more than your total of{" "}
                  {org.contributions_total} items contributed.
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <StatsCard
                title="Total Contributions"
                value={org.contributions_total}
                subtitle="Approved items from your org"
                trend={org.contributions_total > 0 ? "up" : "neutral"}
              />
              <StatsCard
                title="Retrieved by Others"
                value={org.retrievals_by_others}
                subtitle="Times your knowledge helped others"
                trend={org.retrievals_by_others > 0 ? "up" : "neutral"}
              />
              <StatsCard
                title="Helpful Ratio"
                value={totalFeedback > 0 ? `${helpfulPercent}%` : "No feedback yet"}
                subtitle={
                  totalFeedback > 0
                    ? `${org.helpful_count} helpful / ${org.not_helpful_count} not helpful`
                    : "Feedback from retrieval events"
                }
                trend={helpfulPercent >= 70 ? "up" : helpfulPercent >= 40 ? "neutral" : "down"}
              />
              <StatsCard
                title="Approved (24h)"
                value={org.contributions_approved_24h}
                subtitle="Items approved in the last 24 hours"
              />
              <StatsCard
                title="Pending Review"
                value={org.contributions_pending}
                subtitle="Contributions awaiting approval"
                trend={org.contributions_pending > 5 ? "down" : "neutral"}
              />
            </div>

            {/* Top items table */}
            {org.top_items.length > 0 && (
              <div className="mt-6 bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">
                    Top Items by Retrieval Count
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                      <tr>
                        <th className="px-5 py-3 text-left font-medium">Title</th>
                        <th className="px-5 py-3 text-right font-medium">Retrievals</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {org.top_items.map((item) => (
                        <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-5 py-3 text-gray-800 max-w-xs truncate">
                            {item.title}
                          </td>
                          <td className="px-5 py-3 text-right font-semibold text-indigo-700 tabular-nums">
                            {item.retrieval_count.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {org.top_items.length === 0 && org.contributions_total === 0 && (
              <div className="mt-4 text-center py-10 bg-white rounded-lg border border-dashed border-gray-300">
                <p className="text-sm text-gray-500">
                  No contributions yet. Start contributing knowledge to see your impact!
                </p>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
