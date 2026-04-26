import { useEffect, useRef, useCallback } from "react";
import * as Blockly from "blockly";
import { registerBlocks } from "./blocks";
import { toolbox } from "./toolbox";
import { workspaceToCommands } from "./generators/json";
import { runProgram } from "../../services/programRunner";
import { useProgramStore } from "../../stores/programStore";
import { useRobotStore } from "../../stores/robotStore";

let blocksRegistered = false;

export function BlocklyEditor() {
  const containerRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<Blockly.WorkspaceSvg | null>(null);
  const isRunning = useProgramStore((s) => s.isRunning);
  const status = useRobotStore((s) => s.status);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!blocksRegistered) {
      registerBlocks();
      blocksRegistered = true;
    }

    const ws = Blockly.inject(containerRef.current, {
      toolbox,
      theme: Blockly.Themes.Classic,
      renderer: "zelos",
      grid: { spacing: 20, length: 3, colour: "#1f2937", snap: true },
      zoom: { controls: true, wheel: true, startScale: 0.9, maxScale: 2, minScale: 0.3 },
      move: { scrollbars: true, drag: true, wheel: true },
      trashcan: true,
    });

    workspaceRef.current = ws;

    return () => {
      ws.dispose();
      workspaceRef.current = null;
    };
  }, []);

  const handleRun = useCallback(() => {
    if (!workspaceRef.current) return;
    const commands = workspaceToCommands(workspaceRef.current);
    if (commands.length === 0) {
      useRobotStore.getState().addLog("Нет блоков для выполнения", "warn");
      return;
    }
    useProgramStore.getState().setCommands(commands);
    runProgram(commands);
  }, []);

  const handleStop = useCallback(() => {
    useProgramStore.getState().setRunning(false);
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Controls bar */}
      <div className="flex items-center gap-2 p-2 bg-gray-900 border-b border-gray-800 shrink-0">
        <span className="text-[10px] text-gray-500 uppercase tracking-wider mr-auto">
          Block Programming
        </span>
        {isRunning ? (
          <button
            onClick={handleStop}
            className="bg-red-600 hover:bg-red-700 text-white text-xs px-3 py-1 rounded"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleRun}
            disabled={status !== "connected"}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-700 disabled:text-gray-500
              text-white text-xs px-3 py-1 rounded transition-colors"
          >
            Run
          </button>
        )}
      </div>

      {/* Blockly workspace */}
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}
