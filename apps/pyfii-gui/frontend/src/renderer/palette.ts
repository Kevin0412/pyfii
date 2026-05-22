function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const hue = ((h % 360) + 360) % 360;
  const chroma = (1 - Math.abs(2 * l - 1)) * s;
  const x = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
  const match = l - chroma / 2;
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

export function droneColor(id: number, shade = 0): string {
  const hue = 180 - ((id - 1) * 180) / 7;
  const lightness = clamp(0.52 + shade * 0.22, 0.22, 0.75);
  const [r, g, b] = hslToRgb(hue, 0.9, lightness);
  return `rgb(${r}, ${g}, ${b})`;
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
