import { useState, useCallback } from "react";
import { Header } from "./components/layout/Header";
import { BottomBar } from "./components/layout/BottomBar";
import { RobotScene } from "./components/viewer3d/RobotScene";
import { BlocklyEditor } from "./components/blockly/BlocklyEditor";

export default function App() {
  const [splitPercent, setSplitPercent] = useState(65);
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback(() => setIsDragging(true), []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      const container = e.currentTarget as HTMLElement;
      const rect = container.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.max(30, Math.min(80, pct)));
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      <Header />

      {/* Main content: 3D viewer | Blockly */}
      <div
        className="flex flex-1 min-h-0 overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* 3D Viewer */}
        <div
          style={{ width: `${splitPercent}%` }}
          className="h-full overflow-hidden"
        >
          <RobotScene />
        </div>

        {/* Splitter handle */}
        <div
          onMouseDown={handleMouseDown}
          className={`w-1 cursor-col-resize hover:bg-emerald-500/50 transition-colors shrink-0 ${
            isDragging ? "bg-emerald-500/50" : "bg-gray-800"
          }`}
        />

        {/* Blockly editor */}
        <div
          style={{ width: `${100 - splitPercent}%` }}
          className="h-full overflow-hidden"
        >
          <BlocklyEditor />
        </div>
      </div>

      <BottomBar />
    </div>
  );
}
