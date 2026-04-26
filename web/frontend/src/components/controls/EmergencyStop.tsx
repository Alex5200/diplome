import { useCallback, useEffect } from "react";
import { api } from "../../services/api";
import { useRobotStore } from "../../stores/robotStore";
import { useProgramStore } from "../../stores/programStore";

export function EmergencyStop() {
  const { setStopped, addLog, status } = useRobotStore();
  const { setRunning } = useProgramStore();

  const handleStop = useCallback(async () => {
    setStopped(true);
    setRunning(false);
    addLog("ЭКСТРЕННАЯ ОСТАНОВКА", "error");
    try {
      await api.stop();
    } catch {
      addLog("Ошибка отправки E-STOP", "error");
    }
  }, [setStopped, setRunning, addLog]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleStop();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleStop]);

  return (
    <button
      onClick={handleStop}
      disabled={status === "disconnected"}
      className="bg-red-600 hover:bg-red-700 disabled:bg-red-900 disabled:opacity-50
        text-white font-bold px-6 py-2 rounded-lg uppercase tracking-wider
        transition-all shadow-lg shadow-red-900/50 active:scale-95
        animate-pulse hover:animate-none"
    >
      E-STOP
    </button>
  );
}
