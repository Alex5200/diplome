import { useEffect, useRef } from "react";
import { useRobotStore } from "../../stores/robotStore";

const LEVEL_COLORS = {
  info: "text-gray-600",
  ok: "text-green-600",
  error: "text-red-600",
  warn: "text-amber-600",
} as const;

export function EventLog() {
  const logs = useRobotStore((s) => s.logs);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="text-xs font-mono space-y-0.5">
      <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-1">
        Event Log
      </div>
      {logs.length === 0 && (
        <div className="text-gray-600">Нет событий</div>
      )}
      {logs.map((log, i) => (
        <div key={i} className={LEVEL_COLORS[log.level]}>
          <span className="text-gray-600">
            [{log.timestamp.toLocaleTimeString()}]
          </span>{" "}
          {log.message}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
