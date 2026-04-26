import { create } from "zustand";
import type { MotorData, MotorConfig, LogEntry, ConnectionStatus } from "../types/robot";
import { DEFAULT_SPEED } from "../utils/constants";

export interface Pose {
  name: string;
  angles: number[];
}

export const PRESET_POSES: Pose[] = [
  { name: "Home", angles: [0, 0, 0, 0, 0, 0] },
  { name: "Up", angles: [0, -90, -90, 0, 0, 0] },
  { name: "Fold", angles: [0, 45, 135, 0, 90, 0] },
  { name: "Reach", angles: [0, -45, -45, 0, -45, 0] },
];

export const DEFAULT_MOTOR_CONFIG: Record<string, MotorConfig> = {
  "joint_0": { motor_id: 1, name: "Base", min_pos: 0, max_pos: 4095, inverted: false },
  "joint_1": { motor_id: 2, name: "Shoulder", min_pos: 0, max_pos: 4095, inverted: false },
  "joint_2": { motor_id: 3, name: "Elbow", min_pos: 0, max_pos: 4095, inverted: false },
  "joint_3": { motor_id: 4, name: "Wrist 1", min_pos: 0, max_pos: 4095, inverted: false },
  "joint_4": { motor_id: 5, name: "Wrist 2", min_pos: 0, max_pos: 4095, inverted: false },
  "joint_5": { motor_id: 6, name: "Gripper", min_pos: 0, max_pos: 4095, inverted: false },
};

interface RobotState {
  // Connection
  status: ConnectionStatus;
  port: string;
  setPort: (port: string) => void;
  setStatus: (status: ConnectionStatus) => void;

  // Speed control (100-3400)
  speed: number;
  setSpeed: (speed: number) => void;

  // Free move mode (torque off)
  freeMode: boolean;
  setFreeMode: (free: boolean) => void;

  // Joint angles (degrees, -180..180)
  jointAngles: number[];
  setJointAngle: (index: number, angle: number) => void;
  setAllAngles: (angles: number[]) => void;

  // Motor telemetry from WebSocket
  motors: Record<string, MotorData>;
  setMotors: (motors: Record<string, MotorData>) => void;

  // Motor config (min/max, inverted)
  motorConfig: Record<string, MotorConfig>;
  setMotorConfig: (config: Record<string, MotorConfig>) => void;
  updateMotorConfig: (key: string, config: Partial<MotorConfig>) => void;

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

  speed: DEFAULT_SPEED,
  setSpeed: (speed) => set({ speed }),

  freeMode: false,
  setFreeMode: (freeMode) => set({ freeMode }),

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

  motorConfig: DEFAULT_MOTOR_CONFIG,
  setMotorConfig: (config) => set({ motorConfig: config }),
  updateMotorConfig: (key, updates) =>
    set((s) => ({
      motorConfig: {
        ...s.motorConfig,
        [key]: { ...s.motorConfig[key], ...updates },
      },
    })),

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
