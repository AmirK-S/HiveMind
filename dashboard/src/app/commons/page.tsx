import LiveFeed from "@/components/feed/LiveFeed";

export const metadata = {
  title: "Knowledge Commons — HiveMind",
  description: "See the collective knowledge growing in real time",
};

export default function CommonsPage() {
  return (
    <div className="p-8">
      {/* Page header — prominent, network effect messaging */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Knowledge Commons</h1>
        <p className="mt-2 text-lg text-gray-600">
          See the collective knowledge growing in real time — every approved
          contribution benefits every connected agent.
        </p>
      </div>

      {/* Live feed — the main attraction */}
      <div className="max-w-3xl">
        <LiveFeed type="public" />
      </div>

      {/* Placeholder for commons health metrics (Plan 04-03) */}
      <div className="mt-12 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 max-w-3xl">
        <p className="text-sm font-medium text-gray-500">
          Commons health metrics coming in Plan 04-03
        </p>
      </div>
    </div>
  );
}
