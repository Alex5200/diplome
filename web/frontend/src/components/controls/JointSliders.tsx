import { useState } from "react";
import { useRobotStore } from "../../stores/robotStore";
import { api } from "../../services/api";
import { JOINT_NAMES, SAFE_ANGLE_LIMITS } from "../../utils/constants";
import { angleToPosition } from "../../utils/kinematics";

export function JointSliders() {
  const { jointAngles, setJointAngle, speed, addLog, status, motorConfig, freeMode } = useRobotStore();
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingJoint, setPendingJoint] = useState<number | null>(null);
  const isConnected = status === "connected";

  const validatePosition = (index: number): { valid: boolean; message: string } => {
    const config = motorConfig[`joint_${index}`];
    if (!config) return { valid: true, message: "" };

    const pos = angleToPosition(jointAngles[index]);
    if (pos < 0 || pos > 4095) {
      return { valid: false, message: `Позиция ${pos} вне диапазона 0-4095` };
    }
    if (config.min_pos > 0 && pos < config.min_pos) {
      return { valid: false, message: `Позиция ${pos} < мин ${config.min_pos}` };
    }
    if (config.max_pos < 4095 && pos > config.max_pos) {
      return { valid: false, message: `Позиция ${pos} > макс ${config.max_pos}` };
    }
    return { valid: true, message: "" };
  };

  const handleSend = async (index: number) => {
    const validation = validatePosition(index);
    if (!validation.valid) {
      addLog(validation.message, "error");
      return;
    }
    setPendingJoint(index);
    setShowConfirm(true);
  };

  const executeMove = async () => {
    if (pendingJoint === null) return;
    setShowConfirm(false);
    const index = pendingJoint;
    const angle = jointAngles[index];
    const config = motorConfig[`joint_${index}`];

    let pos = angleToPosition(angle);
    if (config?.inverted) {
      pos = 4095 - pos;
    }

    try {
      await api.move({
        joint: index + 1,
        position: pos,
        speed: speed,
      });
      addLog(`J${index + 1} → ${angle.toFixed(1)}° (${speed})`, "ok");
    } catch (e) {
      addLog(`Ошибка J${index + 1}: ${e instanceof Error ? e.message : String(e)}`, "error");
    }

    setPendingJoint(null);
  };

  const cancelMove = () => {
    setShowConfirm(false);
    setPendingJoint(null);
  };

  return (
    <div className="space-y-1">
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-4 max-w-sm">
            <p className="text-gray-800 font-medium mb-2">
              Подтвердите движение
            </p>
            <p className="text-gray-600 text-sm mb-2">
              Сустав {JOINT_NAMES[pendingJoint ?? 0]} переместится в {jointAngles[pendingJoint ?? 0].toFixed(1)}°
            </p>
            <p className="text-amber-600 text-xs mb-3">Скорость: {speed}</p>
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

      {JOINT_NAMES.map((name, i) => {
        const [min, max] = SAFE_ANGLE_LIMITS[i];
        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-gray-600 truncate">{name}</span>
            <input
              type="range"
              min={min}
              max={max}
              step={0.5}
              value={jointAngles[i]}
              onChange={(e) => setJointAngle(i, Number(e.target.value))}
              className="flex-1 h-1.5 accent-emerald-600"
            />
            <span className="w-14 text-right font-mono text-gray-700">
              {jointAngles[i].toFixed(1)}°
            </span>
            <button
              onClick={() => handleSend(i)}
              disabled={!isConnected || freeMode}
              className={`${
                freeMode
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-400"
              } text-white text-xs px-2 py-0.5 rounded transition-colors`}
            >
              {freeMode ? "🔓" : "Go"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
