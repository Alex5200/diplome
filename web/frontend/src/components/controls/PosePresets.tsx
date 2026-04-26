import { useState } from "react";
import { useRobotStore, PRESET_POSES } from "../../stores/robotStore";
import { api } from "../../services/api";
import { angleToPosition, forwardKinematics } from "../../utils/kinematics";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  speed: number;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmModal({ open, title, message, speed, onConfirm, onCancel }: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-4 max-w-sm">
        <p className="text-gray-800 font-medium mb-2">{title}</p>
        <p className="text-gray-600 text-sm mb-2">{message}</p>
        <p className="text-amber-600 text-xs mb-3">Скорость: {speed}</p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-3 py-1 text-gray-600 hover:bg-gray-100 rounded"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700"
          >
            Подтвердить
          </button>
        </div>
      </div>
    </div>
  );
}

export function PosePresets() {
  const { setAllAngles, speed, addLog, status, setIkTarget, motorConfig } = useRobotStore();
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingAngles, setPendingAngles] = useState<number[] | null>(null);
  const [pendingName, setPendingName] = useState("");
  const isConnected = status === "connected";

  const validatePose = (angles: number[]): { valid: boolean; message: string } => {
    for (let i = 0; i < angles.length; i++) {
      const config = motorConfig[`joint_${i}`];
      if (!config) continue;

      const pos = angleToPosition(angles[i]);
      if (pos < 0 || pos > 4095) {
        return { valid: false, message: `J${i + 1}: поз ${pos} вне 0-4095` };
      }
      if (config.min_pos > 0 && pos < config.min_pos) {
        return { valid: false, message: `J${i + 1}: поз ${pos} < мин ${config.min_pos}` };
      }
      if (config.max_pos < 4095 && pos > config.max_pos) {
        return { valid: false, message: `J${i + 1}: поз ${pos} > макс ${config.max_pos}` };
      }
    }
    return { valid: true, message: "" };
  };

  const handlePreset = async (angles: number[], name: string) => {
    const validation = validatePose(angles);
    if (!validation.valid) {
      addLog(validation.message, "error");
      return;
    }
    setPendingAngles(angles);
    setPendingName(name);
    setShowConfirm(true);
  };

  const executeMove = async () => {
    if (!pendingAngles) return;
    setShowConfirm(false);
    setAllAngles(pendingAngles);

    try {
      const positions = pendingAngles.map((a, i) => {
        const config = motorConfig[`joint_${i}`];
        let pos = angleToPosition(a);
        if (config?.inverted) {
          pos = 4095 - pos;
        }
        return pos;
      });
      await api.moveAll({ positions, speed });
      const fk = forwardKinematics(pendingAngles);
      const end = fk[5];
      setIkTarget([end[0], end[1], end[2]] as [number, number, number]);
      addLog(`Поз: ${pendingName} (${pendingAngles.map((a) => a.toFixed(0)).join(", ")}°)`, "ok");
    } catch (e) {
      addLog(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    }

    setPendingAngles(null);
  };

  const cancelMove = () => {
    setShowConfirm(false);
    setPendingAngles(null);
  };

  return (
    <>
      <ConfirmModal
        open={showConfirm}
        title={`Переход в ${pendingName}`}
        message="Робот начнёт движение. Убедитесь, что путь свободен."
        speed={speed}
        onConfirm={executeMove}
        onCancel={cancelMove}
      />
      <div className="flex gap-1 flex-wrap">
        {PRESET_POSES.map((pose) => (
          <button
            key={pose.name}
            onClick={() => handlePreset(pose.angles, pose.name)}
            disabled={!isConnected}
            className="bg-gray-200 hover:bg-gray-300 disabled:bg-gray-100 disabled:text-gray-400
              text-gray-700 text-xs px-2 py-1 rounded transition-colors"
          >
            {pose.name}
          </button>
        ))}
      </div>
    </>
  );
}
