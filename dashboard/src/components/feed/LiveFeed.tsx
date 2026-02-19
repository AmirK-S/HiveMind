"use client";

import { useEffect, useRef, useState } from "react";
import type { FeedEvent } from "@/lib/api";
import FeedItem from "./FeedItem";

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "error";

const MAX_FEED_ITEMS = 100;

interface LiveFeedProps {
  type: "public" | "private";
}

export default function LiveFeed({ type }: LiveFeedProps) {
  const [items, setItems] = useState<FeedEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const eventSource = new EventSource("/api/stream/feed");
    esRef.current = eventSource;

    eventSource.addEventListener("open", () => {
      setStatus("connected");
    });

    // Listen for typed events matching our feed type
    const eventName = type === "public" ? "public" : "private";

    eventSource.addEventListener(eventName, (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as FeedEvent;
        setItems((prev) => {
          const updated = [{ ...data, type }, ...prev];
          return updated.slice(0, MAX_FEED_ITEMS);
        });
      } catch {
        // Ignore malformed events
      }
    });

    eventSource.addEventListener("error", () => {
      if (eventSource.readyState === EventSource.CONNECTING) {
        setStatus("reconnecting");
      } else {
        setStatus("error");
      }
    });

    return () => {
      eventSource.close();
    };
  }, [type]);

  return (
    <div className="space-y-4">
      {/* Connection status indicator */}
      <div className="flex items-center gap-2">
        <span
          className={[
            "inline-block h-2 w-2 rounded-full",
            status === "connected" ? "bg-green-500" : "",
            status === "connecting" ? "bg-yellow-400 animate-pulse" : "",
            status === "reconnecting" ? "bg-orange-400 animate-pulse" : "",
            status === "error" ? "bg-red-400" : "",
          ].join(" ")}
        />
        <span className="text-sm text-gray-500 capitalize">
          {status === "connected"
            ? "Connected — updates are live"
            : status === "connecting"
            ? "Connecting..."
            : status === "reconnecting"
            ? "Reconnecting..."
            : "Connection error"}
        </span>
      </div>

      {/* Feed items */}
      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-sm text-gray-500">
            {status === "connected"
              ? "Waiting for new knowledge to be approved..."
              : "Establishing connection..."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <FeedItem key={item.id} event={item} />
          ))}
        </div>
      )}
    </div>
  );
}
