import { useRobotStore } from "../../stores/robotStore";
import { api } from "../../services/api";
import { wsManager } from "../../services/websocket";

export function ConnectionPanel() {
  const { status, port, setPort, setStatus, addLog, setMotors } =
    useRobotStore();

  const handleConnect = async () => {
    setStatus("connecting");
    try {
      const res = await api.connect({ port });
      setStatus("connected");
      addLog(`Подключено. Моторы: ${res.motors_found?.join(", ")}`, "ok");
      wsManager.connect();
      wsManager.onTelemetry((msg) => setMotors(msg.motors));
    } catch (e) {
      setStatus("error");
      addLog(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  };

  const handleDisconnect = async () => {
    wsManager.disconnect();
    await api.disconnect().catch(() => {});
    setStatus("disconnected");
    addLog("Отключено");
  };

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";

  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-2.5 h-2.5 rounded-full ${
          isConnected
            ? "bg-green-400 shadow-green-400/50 shadow-sm"
            : status === "error"
              ? "bg-red-400"
              : "bg-gray-500"
        }`}
      />
      <input
        value={port}
        onChange={(e) => setPort(e.target.value)}
        placeholder="COM3"
        disabled={isConnected}
        className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded px-2 py-1 w-36
          focus:border-blue-500 focus:outline-none disabled:opacity-50"
      />
      {!isConnected ? (
        <button
          onClick={handleConnect}
          disabled={isConnecting}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900
            text-white text-sm px-3 py-1 rounded transition-colors"
        >
          {isConnecting ? "..." : "Connect"}
        </button>
      ) : (
        <button
          onClick={handleDisconnect}
          className="bg-gray-600 hover:bg-gray-700 text-white text-sm px-3 py-1 rounded transition-colors"
        >
          Disconnect
        </button>
      )}
    </div>
  );
}
