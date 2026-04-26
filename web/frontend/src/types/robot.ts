export interface MotorData {
  position: number;
  temperature: number | null;
  voltage: number | null;
  current: number | null;
  load: number | null;
  status: string;
}

export interface MotorConfig {
  motor_id: number;
  name: string;
  min_pos: number;
  max_pos: number;
  inverted: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
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

export interface MoveAllRequest {
  positions: number[];
  speed: number;
}

export interface TorqueRequest {
  motor_id: number;
  enable: boolean;
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
