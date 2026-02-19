"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  prominent?: boolean;
}

const navItems: NavItem[] = [
  { href: "/commons", label: "Knowledge Commons", icon: "🌐", prominent: true },
  { href: "/dashboard", label: "My Namespace", icon: "🏢" },
  { href: "/search", label: "Search", icon: "🔍" },
  { href: "/contributions", label: "Contributions", icon: "📝" },
  { href: "/analytics", label: "Analytics", icon: "📊" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-gray-200 bg-white px-4 py-6">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-gray-900">HiveMind</h1>
        <p className="text-xs text-gray-500">Knowledge Commons Dashboard</p>
      </div>

      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const isProminent = item.prominent;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-600 text-white"
                  : isProminent
                  ? "bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                  : "text-gray-700 hover:bg-gray-100",
              ].join(" ")}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {isProminent && !isActive && (
                <span className="ml-auto rounded-full bg-indigo-200 px-1.5 py-0.5 text-xs text-indigo-700">
                  Live
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
