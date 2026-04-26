import type {
  ConnectRequest,
  MoveRequest,
  MoveAllRequest,
  IKRequest,
  IKResponse,
  TorqueRequest,
  MotorConfig,
  TokenResponse,
} from "../types/robot";

const BASE = import.meta.env.VITE_API_URL || "";

let authToken = "";
let limitedSecret = "";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  } else if (limitedSecret) {
    headers["Authorization"] = `Bearer ${limitedSecret}`;
  }
  const url = path.startsWith("http") ? path : `${BASE}${path}`;
  const res = await fetch(url, {
    headers,
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  login: async (username: string, password: string): Promise<TokenResponse> => {
    const res = await fetch(`/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json() as TokenResponse;
    authToken = data.access_token;
    localStorage.setItem("authToken", authToken);
    return data;
  },

  logout: () => {
    authToken = "";
    limitedSecret = "";
    localStorage.removeItem("authToken");
    localStorage.removeItem("limitedSecret");
  },

  getToken: () => authToken,

  loadToken: () => {
    authToken = localStorage.getItem("authToken") || "";
    limitedSecret = localStorage.getItem("limitedSecret") || "";
    return authToken;
  },

  setLimitedSecret: (secret: string) => {
    limitedSecret = secret;
    localStorage.setItem("limitedSecret", secret);
  },

  getStatus: () =>
    request<{ connected: boolean; motors: Record<string, unknown> }>(
      "/api/status"
    ),

  connect: (data: ConnectRequest) =>
    request<{ connected: boolean; motors_found: number[] }>("/api/connect", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  disconnect: () =>
    request<{ connected: boolean }>("/api/disconnect", { method: "POST" }),

  scan: () =>
    request<{ found_servos: number[] }>("/api/scan", { method: "POST" }),

  move: (data: MoveRequest) =>
    request<{ joint: number; position: number }>("/api/move", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  moveAll: (data: MoveAllRequest) =>
    request<{ positions: number[] }>("/api/move_all", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  torque: (req: TorqueRequest) =>
    request<{ motor_id: number; torque_enabled: boolean }>("/api/torque", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  stop: () =>
    request<{ stopped: boolean }>("/api/stop", { method: "POST" }),

  solveIK: (data: IKRequest) =>
    request<IKResponse>("/api/ik", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getConfig: () =>
    request<{ motor_mapping: Record<string, MotorConfig> }>("/api/config", {
      method: "POST",
    }),

  setSpeed: (speed: number) =>
    request<{ speed: number }>("/api/config/speed?speed=" + speed, {
      method: "POST",
    }),
};
