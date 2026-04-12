export interface MotorData {
  position: number;
  temperature: number | null;
  voltage: number | null;
  current: number | null;
  load: number | null;
  status: string;
}

export interface TelemetryMessage {
  type: "telemetry";
  motors: Record<string, MotorData>;
}

export interface ConnectRequest {
  port: string;
  baudrate?: number;
}

export interface MoveRequest {
  joint: number;
  position: number;
  speed: number;
}

export interface IKRequest {
  x: number;
  y: number;
  z: number;
}

export interface IKResponse {
  angles_deg: number[];
  error_mm: number;
}

export interface ProgramCommand {
  type: "move" | "move_ik" | "wait" | "home" | "gripper";
  params: Record<string, number | string | boolean>;
}

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export interface LogEntry {
  timestamp: Date;
  message: string;
  level: "info" | "ok" | "error" | "warn";
}
