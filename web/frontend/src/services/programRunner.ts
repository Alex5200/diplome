import type { ProgramCommand } from "../types/robot";
import { api } from "./api";
import { useRobotStore } from "../stores/robotStore";
import { useProgramStore } from "../stores/programStore";

function angleToPosition(angleDeg: number): number {
  return Math.round(((angleDeg + 180) / 360) * 4095);
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export async function runProgram(commands: ProgramCommand[]) {
  const { addLog, setStopped } = useRobotStore.getState();
  const { setRunning, setCurrentStep } = useProgramStore.getState();

  setRunning(true);
  setStopped(false);
  addLog("Программа запущена", "ok");

  for (let i = 0; i < commands.length; i++) {
    const { isStopped } = useRobotStore.getState();
    const { isRunning } = useProgramStore.getState();
    if (isStopped || !isRunning) {
      addLog("Программа остановлена", "warn");
      break;
    }

    setCurrentStep(i);
    const cmd = commands[i];

    try {
      switch (cmd.type) {
        case "move": {
          const joint = cmd.params.joint as number;
          const angle = cmd.params.angle as number;
          const speed = (cmd.params.speed as number) || 2400;
          await api.move({ joint, position: angleToPosition(angle), speed });
          addLog(`J${joint} → ${angle}°`);
          break;
        }
        case "move_ik": {
          const { x, y, z } = cmd.params as { x: number; y: number; z: number };
          const ik = await api.solveIK({ x, y, z });
          for (let j = 0; j < ik.angles_deg.length; j++) {
            await api.move({
              joint: j + 1,
              position: angleToPosition(ik.angles_deg[j]),
              speed: 2400,
            });
          }
          addLog(`IK → (${x}, ${y}, ${z}) err=${ik.error_mm}mm`);
          break;
        }
        case "wait": {
          const ms = ((cmd.params.seconds as number) || 1) * 1000;
          addLog(`Пауза ${ms / 1000}с`);
          await delay(ms);
          break;
        }
        case "home":
          for (let j = 1; j <= 6; j++) {
            await api.move({ joint: j, position: 2048, speed: 2400 });
          }
          addLog("Home позиция");
          break;
        case "gripper": {
          const open = cmd.params.open as boolean;
          addLog(`Захват: ${open ? "открыт" : "закрыт"}`);
          break;
        }
      }
    } catch (e) {
      addLog(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
      break;
    }
  }

  setRunning(false);
  setCurrentStep(-1);
  addLog("Программа завершена", "ok");
}
