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
        <tr className="text-gray-500 border-b border-gray-300">
          <th className="text-left py-1 px-2">ID</th>
          <th className="text-right py-1 px-2">Поз</th>
          <th className="text-right py-1 px-2">°C</th>
          <th className="text-right py-1 px-2">V</th>
          <th className="text-right py-1 px-2">mA</th>
          <th className="text-right py-1 px-2">%</th>
          <th className="text-left py-1 px-2">Статус</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([id, m]) => (
          <tr key={id} className="border-b border-gray-200 hover:bg-gray-100">
            <td className="py-1 px-2 text-gray-700 font-mono">#{id}</td>
            <td className="py-1 px-2 text-right font-mono text-gray-800">
              {m.position}
            </td>
            <td className="py-1 px-2 text-right text-gray-600">
              {m.temperature?.toFixed(1) ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-600">
              {m.voltage?.toFixed(2) ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-600">
              {m.current ?? "—"}
            </td>
            <td className="py-1 px-2 text-right text-gray-600">
              {m.load ?? "—"}
            </td>
            <td className="py-1 px-2 text-gray-600">{m.status ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
