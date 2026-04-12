import { DH_TABLE } from "./constants";

type Vec3 = [number, number, number];
type Mat4 = number[][];

function identity(): Mat4 {
  return [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];
}

function dhMatrix(theta: number, d: number, a: number, alpha: number): Mat4 {
  const ct = Math.cos(theta);
  const st = Math.sin(theta);
  const ca = Math.cos(alpha);
  const sa = Math.sin(alpha);
  return [
    [ct, -st * ca, st * sa, a * ct],
    [st, ct * ca, -ct * sa, a * st],
    [0, sa, ca, d],
    [0, 0, 0, 1],
  ];
}

function multiply(a: Mat4, b: Mat4): Mat4 {
  const r: Mat4 = identity();
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      r[i][j] = 0;
      for (let k = 0; k < 4; k++) {
        r[i][j] += a[i][k] * b[k][j];
      }
    }
  }
  return r;
}

/**
 * Forward kinematics — портировано из app/models/kinematics.py
 * @param anglesDeg — 6 углов суставов в градусах
 * @returns массив из 7 позиций (база + 6 суставов) в мм
 */
export function forwardKinematics(anglesDeg: number[]): Vec3[] {
  const positions: Vec3[] = [[0, 0, 0]]; // база
  let T = identity();

  for (let i = 0; i < 6; i++) {
    const theta = (anglesDeg[i] * Math.PI) / 180;
    const [d, a, alpha] = DH_TABLE[i];
    const Ti = dhMatrix(theta, d, a, alpha);
    T = multiply(T, Ti);
    positions.push([T[0][3], T[1][3], T[2][3]]);
  }

  return positions;
}

/**
 * Конвертация позиции мотора (0-4095) в угол (-180..180°)
 */
export function positionToAngle(pos: number): number {
  return (pos / 4095) * 360 - 180;
}

/**
 * Конвертация угла (-180..180°) в позицию мотора (0-4095)
 */
export function angleToPosition(angle: number): number {
  return Math.round(((angle + 180) / 360) * 4095);
}
