import { useState } from "react";
import { ConnectionPanel } from "../controls/ConnectionPanel";
import { EmergencyStop } from "../controls/EmergencyStop";
import { PosePresets } from "../controls/PosePresets";
import { MotorConfigPanel } from "../controls/MotorConfigPanel";
import { useRobotStore } from "../../stores/robotStore";

interface HeaderProps {
  onToggleBlockly?: () => void;
  blocklyVisible?: boolean;
}

export function Header({ onToggleBlockly, blocklyVisible = true }: HeaderProps) {
  const { isStopped, setStopped, speed, setSpeed } = useRobotStore();
  const [showConfig, setShowConfig] = useState(false);

  return (
    <>
      {showConfig && <MotorConfigPanel onClose={() => setShowConfig(false)} />}
      <header className="bg-white border-b border-gray-300 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-base font-semibold text-emerald-600 tracking-wide">
            ST3215 Robot Control
          </h1>
          <ConnectionPanel />
        </div>

        <div className="flex items-center gap-3">
          {/* Speed control */}
          <div className="flex items-center gap-1 text-xs text-gray-600">
            <span>Speed:</span>
            <input
              type="range"
              min={100}
              max={3400}
              step={100}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="w-20 h-1.5 accent-blue-600"
            />
            <span className="w-8 font-mono">{speed}</span>
          </div>

          {/* Pose presets */}
          <PosePresets />

          {/* Motor config */}
          <button
            onClick={() => setShowConfig(true)}
            className="bg-gray-500 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
            title="Конфигурация моторов"
          >
            ⚙️
          </button>

          {/* Toggle Blockly */}
          <button
            onClick={onToggleBlockly}
            className={`text-xs px-2 py-1 rounded ${
              blocklyVisible
                ? "bg-emerald-600 text-white"
                : "bg-gray-400 text-white hover:bg-gray-500"
            }`}
            title={blocklyVisible ? "Скрыть Blockly" : "Показать Blockly"}
          >
            {blocklyVisible ? "▼ Blockly" : "▲ Blockly"}
          </button>

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
    </>
  );
}
