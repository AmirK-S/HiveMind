interface StatsCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
}

const TREND_ICONS = {
  up: "↑",
  down: "↓",
  neutral: "→",
};

const TREND_COLORS = {
  up: "text-green-600",
  down: "text-red-600",
  neutral: "text-gray-500",
};

export default function StatsCard({ title, value, subtitle, trend }: StatsCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-gray-600">{title}</p>
        {trend && (
          <span className={`text-lg font-bold ${TREND_COLORS[trend]}`}>
            {TREND_ICONS[trend]}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <p className="text-3xl font-bold text-gray-900 tabular-nums">
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
      </div>
      {subtitle && (
        <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
      )}
    </div>
  );
}
