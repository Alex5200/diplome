import { useRobotStore } from "../../stores/robotStore";

export function MotorTable() {
  const motors = useRobotStore((s) => s.motors);
  const entries = Object.entries(motors);

  if (entries.length === 0) {
    return (
      <div className="text-gray-500 text-xs p-2">Нет данных телеметрии</div>
    );
  }

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-gray-500 border-b border-gray-800">
          <th className="text-left py-1 px-2">Motor</th>
          <th className="text-right py-1 px-2">Pos</th>
          <th className="text-right py-1 px-2">T °C</th>
          <th className="text-right py-1 px-2">V</th>
          <th className="text-right py-1 px-2">mA</th>
          <th className="text-right py-1 px-2">Load</th>
          <th className="text-left py-1 px-2">Status</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([id, m]) => (
          <tr key={id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
            <td className="py-1 px-2 text-gray-300">M{id}</td>
            <td className="py-1 px-2 text-right font-mono text-gray-200">
              {m.position}
            </td>
            <td className="py-1 px-2 text-right text-gray-400">
              {m.temperature?.toFixed(1) ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-400">
              {m.voltage?.toFixed(2) ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-400">
              {m.current ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-400">
              {m.load ?? "—"}
            </td>
            <td className="py-1 px-2 text-gray-400">{m.status ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
