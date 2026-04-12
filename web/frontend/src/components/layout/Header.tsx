import { ConnectionPanel } from "../controls/ConnectionPanel";
import { EmergencyStop } from "../controls/EmergencyStop";
import { useRobotStore } from "../../stores/robotStore";

export function Header() {
  const { isStopped, setStopped } = useRobotStore();

  return (
    <header className="bg-gray-900 border-b border-gray-800 px-4 py-2 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-4">
        <h1 className="text-base font-semibold text-emerald-400 tracking-wide">
          ST3215 Robot Control
        </h1>
        <ConnectionPanel />
      </div>
      <div className="flex items-center gap-3">
        {isStopped && (
          <button
            onClick={() => setStopped(false)}
            className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-3 py-1 rounded"
          >
            Reset
          </button>
        )}
        <EmergencyStop />
      </div>
    </header>
  );
}
