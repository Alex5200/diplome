import { useRobotStore } from "../../stores/robotStore";
import { api } from "../../services/api";
import { JOINT_NAMES, SAFE_ANGLE_LIMITS } from "../../utils/constants";
import { angleToPosition } from "../../utils/kinematics";

export function JointSliders() {
  const { jointAngles, setJointAngle, addLog, status } = useRobotStore();
  const isConnected = status === "connected";

  const handleSend = async (index: number) => {
    const angle = jointAngles[index];
    try {
      await api.move({
        joint: index + 1,
        position: angleToPosition(angle),
        speed: 2400,
      });
      addLog(`J${index + 1} → ${angle.toFixed(1)}°`, "ok");
    } catch (e) {
      addLog(`Ошибка J${index + 1}: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  };

  return (
    <div className="space-y-1">
      {JOINT_NAMES.map((name, i) => {
        const [min, max] = SAFE_ANGLE_LIMITS[i];
        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-gray-400 truncate">{name}</span>
            <input
              type="range"
              min={min}
              max={max}
              step={0.5}
              value={jointAngles[i]}
              onChange={(e) => setJointAngle(i, Number(e.target.value))}
              className="flex-1 h-1.5 accent-emerald-400"
            />
            <span className="w-14 text-right font-mono text-gray-300">
              {jointAngles[i].toFixed(1)}°
            </span>
            <button
              onClick={() => handleSend(i)}
              disabled={!isConnected}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-700
                text-white text-xs px-2 py-0.5 rounded transition-colors"
            >
              Go
            </button>
          </div>
        );
      })}
    </div>
  );
}
