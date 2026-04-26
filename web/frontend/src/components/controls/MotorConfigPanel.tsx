import { useState, useEffect } from "react";
import { useRobotStore, DEFAULT_MOTOR_CONFIG } from "../../stores/robotStore";
import { api } from "../../services/api";
import { JOINT_NAMES } from "../../utils/constants";

interface MotorConfigPanelProps {
  onClose: () => void;
}

export function MotorConfigPanel({ onClose }: MotorConfigPanelProps) {
  const { motorConfig, updateMotorConfig, addLog, motors, status } = useRobotStore();
  const [openJoint, setOpenJoint] = useState<number | null>(null);
  const [discoveredMotors, setDiscoveredMotors] = useState<number[]>([]);

  const handleChange = (key: string, field: string, value: number | boolean) => {
    updateMotorConfig(key, { [field]: value });
  };

  const discoverMotors = async () => {
    try {
      const res = await api.scan();
      const found = res.found_servos || [];
      setDiscoveredMotors(found);
      addLog(`Найдены моторы: ${found.join(", ") || "нет"}`, "info");

      found.forEach((mid, idx) => {
        if (idx < 6) {
          updateMotorConfig(`joint_${idx}`, { motor_id: mid });
        }
      });
    } catch (e) {
      addLog(`Ошибка сканирования: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  };

  const discoverFromStatus = () => {
    const found: number[] = [];
    Object.keys(motors).forEach((key) => {
      const id = parseInt(key);
      if (!isNaN(id)) found.push(id);
    });
    setDiscoveredMotors(found);
    addLog(`Из status: ${found.join(", ") || "нет"} моторов`, "info");

    found.forEach((mid, idx) => {
      if (idx < 6) {
        updateMotorConfig(`joint_${idx}`, { motor_id: mid });
      }
    });
  };

  useEffect(() => {
    if (status === "connected" && Object.keys(motors).length > 0) {
      discoverFromStatus();
    }
  }, [status]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-4 w-[500px] max-h-[80vh] overflow-auto">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-lg font-semibold text-gray-800">
            Конфигурация моторов
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        <div className="flex gap-2 mb-3 text-sm">
          <button
            onClick={discoverMotors}
            disabled={status !== "connected"}
            className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
          >
            🔍 Автоопределение
          </button>
          {discoveredMotors.length > 0 && (
            <span className="text-gray-600 self-center">
              Найдены: {discoveredMotors.join(", ")}
            </span>
          )}
        </div>

        <div className="space-y-2 text-sm">
          {Object.entries(motorConfig).map(([key, config], i) => {
            const jointIndex = parseInt(key.replace("joint_", ""));
            const isOpen = openJoint === jointIndex;
            const hasMotor = motors[String(config.motor_id)] !== undefined;

            return (
              <div key={key} className="border border-gray-200 rounded">
                <button
                  onClick={() => setOpenJoint(isOpen ? null : jointIndex)}
                  className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-700">
                      J{jointIndex + 1}: {config.name || JOINT_NAMES[jointIndex]}
                    </span>
                    {hasMotor && status === "connected" && (
                      <span className="text-xs bg-green-100 text-green-700 px-1 rounded">онлайн</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    {config.inverted && <span className="text-amber-600">Инверт</span>}
                    <span>ID:{config.motor_id}</span>
                    <span>{config.min_pos}-{config.max_pos}</span>
                    <span>{isOpen ? "▼" : "▶"}</span>
                  </div>
                </button>

                {isOpen && (
                  <div className="px-3 py-2 space-y-2 border-t border-gray-200">
                    <div className="flex items-center gap-2">
                      <label className="w-20 text-gray-600">ID мотора:</label>
                      <input
                        type="number"
                        value={config.motor_id}
                        onChange={(e) => handleChange(key, "motor_id", Number(e.target.value))}
                        className="w-20 border border-gray-300 rounded px-2 py-1"
                        min={1}
                        max={254}
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="w-20 text-gray-600">Мин поз:</label>
                      <input
                        type="number"
                        value={config.min_pos}
                        onChange={(e) => handleChange(key, "min_pos", Number(e.target.value))}
                        className="w-24 border border-gray-300 rounded px-2 py-1"
                        min={0}
                        max={4095}
                      />
                      <span className="text-gray-400">-</span>
                      <label className="text-gray-600">Макс:</label>
                      <input
                        type="number"
                        value={config.max_pos}
                        onChange={(e) => handleChange(key, "max_pos", Number(e.target.value))}
                        className="w-24 border border-gray-300 rounded px-2 py-1"
                        min={0}
                        max={4095}
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="w-20 text-gray-600">Инверт:</label>
                      <input
                        type="checkbox"
                        checked={config.inverted}
                        onChange={(e) => handleChange(key, "inverted", e.target.checked)}
                        className="w-4 h-4"
                      />
                      <span className="text-xs text-gray-500">
                        {config.inverted
                          ? "Инвертировать направление"
                          : "Обычное направление"}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-4 flex justify-between">
          <button
            onClick={() => {
              Object.keys(DEFAULT_MOTOR_CONFIG).forEach((key) => {
                updateMotorConfig(key, DEFAULT_MOTOR_CONFIG[key]);
              });
              setDiscoveredMotors([]);
              addLog("Конфигурация сброшена", "info");
            }}
            className="px-3 py-1 text-gray-600 hover:bg-gray-100 rounded"
          >
            Сбросить
          </button>
          <button
            onClick={() => {
              addLog("Конфигурация сохранена", "ok");
              onClose();
            }}
            className="px-4 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700"
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}