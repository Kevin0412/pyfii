import type { RenderFrame, RenderOptions } from "../types";
import { canvasPalette, droneColor } from "../palette";
import { PYFII_CLASSIC_LAYOUT } from "./layout";

function fitText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  initialSize: number,
): number {
  for (let size = initialSize; size >= 9; size -= 1) {
    ctx.font = infoFont(size);
    if (ctx.measureText(text).width <= maxWidth) {
      return size;
    }
  }
  return 9;
}

function infoFont(size: number): string {
  return `700 ${size}px "JetBrains Mono", Consolas, monospace`;
}

function drawSplitCellText(
  ctx: CanvasRenderingContext2D,
  text: string,
  textX: number,
  textY: number,
  cellX: number,
  cellY: number,
  cellWidth: number,
  cellHeight: number,
): void {
  const splitX = cellX + cellWidth / 2;

  ctx.save();
  ctx.beginPath();
  ctx.rect(cellX, cellY, splitX - cellX, cellHeight);
  ctx.clip();
  ctx.fillStyle = "#ffffff";
  ctx.fillText(text, textX, textY);
  ctx.restore();

  ctx.save();
  ctx.beginPath();
  ctx.rect(splitX, cellY, cellX + cellWidth - splitX, cellHeight);
  ctx.clip();
  ctx.fillStyle = "#000000";
  ctx.fillText(text, textX, textY);
  ctx.restore();
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
  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const x = grid.x + col * grid.cellWidth;
      const y = grid.y + row * grid.cellHeight;
      const cellIndex = row * grid.cols + col + 1;
      if (cellIndex <= 9) {
        const gradient = ctx.createLinearGradient(x, y, x + grid.cellWidth, y);
        gradient.addColorStop(0, droneColor(cellIndex, -125));
        gradient.addColorStop(0.5, droneColor(cellIndex, 0));
        gradient.addColorStop(1, droneColor(cellIndex, 125));
        ctx.fillStyle = gradient;
      } else {
        ctx.fillStyle = "rgba(0, 0, 0, 0.82)";
      }
      ctx.fillRect(x, y, grid.cellWidth, grid.cellHeight);
      ctx.strokeRect(x, y, grid.cellWidth, grid.cellHeight);
    }
  }

  const droneById = new Map(frame.drones.map((drone) => [drone.id, drone]));
  const labels = [1, 2, 3, 4, 5, 6, 7, 8, 9];

  for (const id of labels) {
    const index = id - 1;
    const col = index % 5;
    const row = Math.floor(index / 5);
    const cellX = grid.x + col * grid.cellWidth;
    const cellY = grid.y + row * grid.cellHeight;
    const x = cellX + 6;
    const y = cellY + 20;
    const drone = droneById.get(id);
    if (!drone) {
      continue;
    }

    const label = `D${id} (${Math.round(drone.xCm)},${Math.round(drone.yCm)},${Math.round(drone.zCm)})`;
    const size = fitText(ctx, label, grid.cellWidth - 12, 13);
    ctx.font = infoFont(size);
    drawSplitCellText(
      ctx,
      label,
      x,
      y,
      cellX,
      cellY,
      grid.cellWidth,
      grid.cellHeight,
    );
  }

  const statusX = grid.x + 4 * grid.cellWidth + 6;
  const statusY = grid.y + grid.cellHeight + 12;
  ctx.fillStyle = options.playing ? canvasPalette.ok : canvasPalette.subtleText;
  ctx.font = '12px "JetBrains Mono", Consolas, monospace';
  ctx.fillText(`T+${(frame.timeMs / 1000).toFixed(2)}`, statusX, statusY);
  ctx.fillText(`${options.fps}fps ${options.playing ? "RUN" : "HOLD"}`, statusX, statusY + 13);
  ctx.restore();
}
