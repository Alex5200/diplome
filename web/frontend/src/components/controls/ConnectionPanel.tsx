import { useState, useEffect } from "react";
import { useRobotStore } from "../../stores/robotStore";
import { api } from "../../services/api";
import { wsManager } from "../../services/websocket";
import { positionToAngle } from "../../utils/kinematics";

export function ConnectionPanel() {
  const {
    status,
    port,
    setPort,
    setStatus,
    addLog,
    setMotors,
    setStopped,
    motors,
    setAllAngles,
    freeMode,
    setFreeMode,
    speed,
  } = useRobotStore();
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingMove, setPendingMove] = useState<(() => void) | null>(null);

  useEffect(() => {
    if (status === "connected") {
      api.getStatus().then((res) => {
        if (res.connected) {
          setStatus("connected");
          addLog("Подключение восстановлено", "info");
        }
      }).catch(() => {});
    }
  }, []);

  const handleConnect = async () => {
    try {
      const statusRes = await api.getStatus();
      if (statusRes.connected) {
        setStatus("connected");
        setStopped(false);
        addLog("Уже подключено (восстановлено)", "ok");
        wsManager.connect();
        wsManager.onTelemetry((msg) => setMotors(msg.motors));
        return;
      }
    } catch {
    }

    setStatus("connecting");
    try {
      const res = await api.connect({ port });
      setStatus("connected");
      setStopped(false);
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

const handleScan = async () => {
    try {
      const res = await api.scan();
      addLog(`Найдены моторы: ${res.found_servos?.join(", ") || "нет"}`, "info");
    } catch (e) {
      addLog(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  };

  const handleToggleFreeMode = async () => {
    const newMode = !freeMode;
    try {
      for (let i = 1; i <= 6; i++) {
        await api.torque({ motor_id: i, enable: !newMode });
      }
      setFreeMode(newMode);
      addLog(newMode ? "Свободный режим (момент выкл)" : "Момент включён", newMode ? "warn" : "ok");
    } catch (e) {
      addLog(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  };

  const handleSyncPosition = () => {
    const angles: number[] = [];
    for (let i = 1; i <= 6; i++) {
      const m = motors[String(i)];
      if (m?.position !== undefined) {
        angles.push(positionToAngle(m.position));
      } else {
        angles.push(0);
      }
    }
    setAllAngles(angles);
    addLog("Позиция синхронизирована", "ok");
  };

  const confirmMove = (action: () => void) => {
    setPendingMove(() => action);
    setShowConfirm(true);
  };

  const executeMove = () => {
    setShowConfirm(false);
    if (pendingMove) {
      pendingMove();
      setPendingMove(null);
    }
  };

  const cancelMove = () => {
    setShowConfirm(false);
    setPendingMove(null);
  };

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";

  return (
    <div className="flex items-center gap-2">
      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-4 max-w-sm">
            <p className="text-gray-800 font-medium mb-3">
              Подтвердите движение
            </p>
            <p className="text-gray-600 text-sm mb-3">
              Робот начнёт движение. Убедитесь, что путь свободен.
            </p>
            <p className="text-amber-600 text-xs mb-3">
              Скорость: {speed}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={cancelMove}
                className="px-3 py-1 text-gray-600 hover:bg-gray-100 rounded"
              >
                Отмена
              </button>
              <button
                onClick={executeMove}
                className="px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700"
              >
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}

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
        className="bg-white border border-gray-300 text-gray-800 text-sm rounded px-2 py-1 w-24
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
        <>
          <button
            onClick={handleScan}
            className="bg-gray-500 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded transition-colors"
            title="Сканировать моторы"
          >
            Scan
          </button>
          <button
            onClick={handleToggleFreeMode}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              freeMode
                ? "bg-amber-500 text-white"
                : "bg-gray-500 text-white hover:bg-gray-600"
            }`}
            title={freeMode ? "Включить момент" : "Отключить момент (свободный режим)"}
          >
            {freeMode ? "🔓 Free" : "🔒 Hold"}
          </button>
          <button
            onClick={() => confirmMove(handleSyncPosition)}
            className="bg-amber-500 hover:bg-amber-600 text-white text-xs px-2 py-1 rounded transition-colors"
            title="Синхронизировать позицию"
          >
            Sync
          </button>
          <button
            onClick={handleDisconnect}
            className="bg-gray-600 hover:bg-gray-700 text-white text-sm px-3 py-1 rounded transition-colors"
          >
            Disconnect
          </button>
        </>
      )}
    </div>
  );
}
