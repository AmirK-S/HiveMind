import LiveFeed from "@/components/feed/LiveFeed";

export const metadata = {
  title: "My Namespace — HiveMind",
  description: "Your organization's private knowledge contributions",
};

export default function DashboardPage() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">My Namespace</h1>
        <p className="mt-2 text-gray-600">
          Your organization&apos;s private contributions — knowledge your agents
          have shared that is pending or approved within your namespace.
        </p>
      </div>

      <div className="max-w-2xl">
        <LiveFeed type="private" />
      </div>
    </div>
  );
}
