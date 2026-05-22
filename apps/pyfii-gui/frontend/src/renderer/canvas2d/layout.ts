export const PYFII_CLASSIC_LAYOUT = {
  canvasWidth: 1200,
  canvasHeight: 600,

  topView: {
    x: 0,
    y: 0,
    width: 600,
    height: 600,
  },

  frontView: {
    x: 600,
    y: 0,
    width: 600,
    height: 270,
  },

  rightView: {
    x: 600,
    y: 270,
    width: 600,
    height: 270,
  },

  infoGrid: {
    x: 600,
    y: 540,
    width: 600,
    height: 60,
    rows: 2,
    cols: 5,
    cellWidth: 120,
    cellHeight: 30,
  },
} as const;

export function topViewPoint(xCm: number, yCm: number): [number, number] {
  return [20 + xCm, 580 - yCm];
}

export function frontViewPoint(xCm: number, zCm: number): [number, number] {
  return [620 + xCm, 270 - zCm];
}

export function rightViewPoint(yCm: number, zCm: number): [number, number] {
  return [620 + yCm, 540 - zCm];
}
