import { create } from "zustand";
import type { MotorData, LogEntry, ConnectionStatus } from "../types/robot";

interface RobotState {
  // Connection
  status: ConnectionStatus;
  port: string;
  setPort: (port: string) => void;
  setStatus: (status: ConnectionStatus) => void;

  // Joint angles (degrees, -180..180)
  jointAngles: number[];
  setJointAngle: (index: number, angle: number) => void;
  setAllAngles: (angles: number[]) => void;

  // Motor telemetry from WebSocket
  motors: Record<string, MotorData>;
  setMotors: (motors: Record<string, MotorData>) => void;

  // Emergency stop
  isStopped: boolean;
  setStopped: (stopped: boolean) => void;

  // Event log
  logs: LogEntry[];
  addLog: (message: string, level?: LogEntry["level"]) => void;
  clearLogs: () => void;

  // IK target
  ikTarget: [number, number, number] | null;
  setIkTarget: (target: [number, number, number] | null) => void;
}

export const useRobotStore = create<RobotState>((set) => ({
  status: "disconnected",
  port: "COM3",
  setPort: (port) => set({ port }),
  setStatus: (status) => set({ status }),

  jointAngles: [0, 0, 0, 0, 0, 0],
  setJointAngle: (index, angle) =>
    set((s) => {
      const angles = [...s.jointAngles];
      angles[index] = angle;
      return { jointAngles: angles };
    }),
  setAllAngles: (angles) => set({ jointAngles: angles }),

  motors: {},
  setMotors: (motors) => set({ motors }),

  isStopped: false,
  setStopped: (isStopped) => set({ isStopped }),

  logs: [],
  addLog: (message, level = "info") =>
    set((s) => ({
      logs: [...s.logs.slice(-99), { timestamp: new Date(), message, level }],
    })),
  clearLogs: () => set({ logs: [] }),

  ikTarget: null,
  setIkTarget: (ikTarget) => set({ ikTarget }),
}));
