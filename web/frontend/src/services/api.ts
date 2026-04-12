import type {
  ConnectRequest,
  MoveRequest,
  IKRequest,
  IKResponse,
} from "../types/robot";

const BASE = "";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
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

  move: (data: MoveRequest) =>
    request<{ joint: number; position: number }>("/api/move", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  stop: () =>
    request<{ stopped: boolean }>("/api/stop", { method: "POST" }),

  solveIK: (data: IKRequest) =>
    request<IKResponse>("/api/ik", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
