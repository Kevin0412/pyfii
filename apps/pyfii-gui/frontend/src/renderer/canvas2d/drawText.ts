import type { RenderFrame, RenderOptions } from "../types";
import { canvasPalette } from "../palette";
import { PYFII_CLASSIC_LAYOUT } from "./layout";

function fitText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  initialSize: number,
): number {
  for (let size = initialSize; size >= 9; size -= 1) {
    ctx.font = `${size}px "JetBrains Mono", Consolas, monospace`;
    if (ctx.measureText(text).width <= maxWidth) {
      return size;
    }
  }
  return 9;
}

export function drawPanelText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  size = 15,
  color = canvasPalette.panelText,
): void {
  ctx.save();
  ctx.fillStyle = color;
  ctx.font = `${size}px "JetBrains Mono", Consolas, monospace`;
  ctx.textBaseline = "alphabetic";
  ctx.fillText(text, x, y);
  ctx.restore();
}

export function drawInfoGrid(
  ctx: CanvasRenderingContext2D,
  frame: RenderFrame,
  options: RenderOptions,
): void {
  const grid = PYFII_CLASSIC_LAYOUT.infoGrid;
  ctx.save();
  ctx.strokeStyle = canvasPalette.border;
  ctx.lineWidth = 1;
  ctx.fillStyle = "rgba(0, 0, 0, 0.72)";
  ctx.fillRect(grid.x, grid.y, grid.width, grid.height);

  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const x = grid.x + col * grid.cellWidth;
      const y = grid.y + row * grid.cellHeight;
      ctx.strokeRect(x, y, grid.cellWidth, grid.cellHeight);
    }
  }

  const droneById = new Map(frame.drones.map((drone) => [drone.id, drone]));
  const labels = [1, 2, 3, 4, 5, 6, 7, 8, 9];

  for (const id of labels) {
    const index = id - 1;
    const col = index % 5;
    const row = Math.floor(index / 5);
    const x = grid.x + col * grid.cellWidth + 6;
    const y = grid.y + row * grid.cellHeight + 20;
    const drone = droneById.get(id);
    if (!drone) {
      continue;
    }

    const label = `D${id} (${Math.round(drone.xCm)},${Math.round(drone.yCm)},${Math.round(drone.zCm)})`;
    const size = fitText(ctx, label, grid.cellWidth - 12, 13);
    ctx.fillStyle = id === options.selectedDroneId ? canvasPalette.selected : canvasPalette.panelText;
    ctx.font = `${size}px "JetBrains Mono", Consolas, monospace`;
    ctx.fillText(label, x, y);
  }

  const statusX = grid.x + 4 * grid.cellWidth + 6;
  const statusY = grid.y + grid.cellHeight + 12;
  ctx.fillStyle = options.playing ? canvasPalette.ok : canvasPalette.subtleText;
  ctx.font = '12px "JetBrains Mono", Consolas, monospace';
  ctx.fillText(`T+${(frame.timeMs / 1000).toFixed(2)}`, statusX, statusY);
  ctx.fillText(`${options.fps}fps ${options.playing ? "RUN" : "HOLD"}`, statusX, statusY + 13);
  ctx.restore();
}
