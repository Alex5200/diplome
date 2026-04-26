// DH параметры робота (из app/models/kinematics.py)
export const DH_PARAMS = {
  L0: 19,   // База (мм)
  L1: 104,  // Плечо 1
  L2: 95,   // Плечо 2
  L3: 34,   // Локоть
  L4: 35,   // Запястье
  L5: 0,    // Инструмент
} as const;

// DH таблица: [d, a, alpha]
export const DH_TABLE: [number, number, number][] = [
  [DH_PARAMS.L0, 0, Math.PI / 2],    // J1
  [0, DH_PARAMS.L1, 0],              // J2
  [0, DH_PARAMS.L2, 0],              // J3
  [0, DH_PARAMS.L3, Math.PI / 2],    // J4
  [0, DH_PARAMS.L4, -Math.PI / 2],   // J5
  [DH_PARAMS.L5, 0, 0],              // J6
];

export const NUM_JOINTS = 6;
export const MIN_POSITION = 0;
export const MAX_POSITION = 4095;
export const DEFAULT_SPEED = 2400;

export const SAFE_ANGLE_LIMITS: [number, number][] = [
  [-180, 180],
  [-180, 180],
  [-180, 180],
  [-180, 180],
  [-180, 180],
  [-180, 180],
];

export const JOINT_NAMES = [
  "База (J1)",
  "Плечо 1 (J2)",
  "Плечо 2 (J3)",
  "Локоть (J4)",
  "Кисть 1 (J5)",
  "Кисть 2 (J6)",
];

// Цвета звеньев для 3D
export const LINK_COLORS = [
  "#7dd3c0", "#a8e6cf", "#b8d4e3",
  "#8ab4f8", "#d7bde2", "#f5b971",
];

// Масштаб для Three.js (мм → единицы сцены)
export const SCALE = 0.01;
