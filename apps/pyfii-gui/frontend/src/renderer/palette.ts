function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hsvToRgb(h: number, s: number, v: number): [number, number, number] {
  const hue = ((h % 360) + 360) % 360;
  const saturation = clamp(s, 0, 1);
  const value = clamp(v, 0, 1);
  const chroma = value * saturation;
  const x = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
  const match = value - chroma;
  let r = 0;
  let g = 0;
  let b = 0;

  if (hue < 60) {
    r = chroma;
    g = x;
  } else if (hue < 120) {
    r = x;
    g = chroma;
  } else if (hue < 180) {
    g = chroma;
    b = x;
  } else if (hue < 240) {
    g = x;
    b = chroma;
  } else if (hue < 300) {
    r = x;
    b = chroma;
  } else {
    r = chroma;
    b = x;
  }

  return [
    Math.round((r + match) * 255),
    Math.round((g + match) * 255),
    Math.round((b + match) * 255),
  ];
}

export function droneRgb(id: number, shade = 0): [number, number, number] {
  const zeroBasedId = Math.max(0, id - 1);
  const pyfiiHue = 180 - (zeroBasedId * 180) / 9;
  const hue = ((-Math.abs(pyfiiHue)) % 180) + 180;
  const cvHueDegrees = (hue % 180) * 2;
  const shadeValue = clamp(shade, -125, 125);
  const saturation = shadeValue > 0 ? (255 - shadeValue) / 255 : 1;
  const value = shadeValue > 0 ? 1 : (255 + shadeValue) / 255;
  return hsvToRgb(cvHueDegrees, saturation, value);
}

export function rgbCss(rgb: [number, number, number]): string {
  const [r, g, b] = rgb;
  return `rgb(${r}, ${g}, ${b})`;
}

export function droneColor(id: number, shade = 0): string {
  return rgbCss(droneRgb(id, shade));
}

export function ledColor(rgb: [number, number, number]): string | null {
  if (rgb[0] < 0 && rgb[1] < 0 && rgb[2] < 0) {
    return null;
  }
  return `rgb(${clamp(rgb[0], 0, 255)}, ${clamp(rgb[1], 0, 255)}, ${clamp(rgb[2], 0, 255)})`;
}

export const canvasPalette = {
  background: "#000000",
  border: "#f1f1f1",
  gridDark: "#404040",
  gridLight: "#bfbfbf",
  panelText: "#f1f1f1",
  subtleText: "#9a9a9a",
  warning: "#ffd15c",
  error: "#ff3333",
  ok: "#46d37b",
  selected: "#fff07a",
};
